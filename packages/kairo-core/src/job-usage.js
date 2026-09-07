import { mkdir, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertSafeId } from "./ids.js";
import { parseMarkdown } from "./frontmatter.js";
import { KairoError } from "./errors.js";
import { KairoStore } from "./store.js";

function requireText(value, label) {
  const text = String(value ?? "").trim();
  if (!text) throw new TypeError(`${label} is required.`);
  return text;
}

function optionalText(value) {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function nowIso(clock) {
  return clock().toISOString();
}

async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function atomicWriteJson(filePath, value) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const temp = `${filePath}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  await writeFile(temp, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  await rename(temp, filePath);
}

function jobFile(dataDir, projectSlug, jobId) {
  return path.join(dataDir, "projects", projectSlug, "jobs", `${jobId}.md`);
}

function usageFile(dataDir, projectSlug, jobId) {
  return path.join(dataDir, "projects", projectSlug, "job-usage", `${jobId}.json`);
}

function normalizeCounter(value, label) {
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) throw new TypeError(`${label} must be a non-negative number.`);
  return number;
}

function normalizeUsage(raw = {}) {
  const usage = {};
  for (const [key, label] of [
    ["input", "usage.input"],
    ["output", "usage.output"],
    ["cacheRead", "usage.cacheRead"],
    ["cacheWrite", "usage.cacheWrite"],
    ["total", "usage.total"],
  ]) {
    const value = normalizeCounter(raw?.[key], label);
    if (value !== undefined) usage[key] = value;
  }
  return usage;
}

function addUsage(left = {}, right = {}) {
  const result = {};
  for (const key of ["input", "output", "cacheRead", "cacheWrite", "total"]) {
    const a = Number(left[key] ?? 0);
    const b = Number(right[key] ?? 0);
    if (a || b || key in left || key in right) result[key] = a + b;
  }
  return result;
}

function runAggregate(calls) {
  return calls.reduce((sum, call) => addUsage(sum, call.usage), {});
}

function summarize(state) {
  const totalUsage = {};
  const providerModels = new Set();
  let knownCostUsd = 0;
  let pricedRuns = 0;
  let unpricedRuns = 0;
  let toolCalls = 0;

  for (const run of state.runs ?? []) {
    const effectiveUsage = run.final_snapshot?.usage ?? run.aggregate ?? {};
    Object.assign(totalUsage, addUsage(totalUsage, effectiveUsage));
    const provider = run.final_snapshot?.provider ?? run.provider;
    const model = run.final_snapshot?.model ?? run.model;
    if (provider && model) providerModels.add(`${provider}/${model}`);
    if (run.final_snapshot && Number.isFinite(run.final_snapshot.turn_usd)) {
      knownCostUsd += run.final_snapshot.turn_usd;
      pricedRuns += 1;
    } else {
      unpricedRuns += 1;
    }
    toolCalls += Array.isArray(run.tool_calls) ? run.tool_calls.length : 0;
  }

  return {
    runs: state.runs?.length ?? 0,
    model_calls: (state.runs ?? []).reduce((sum, run) => sum + (run.calls?.length ?? 0), 0),
    tool_calls: toolCalls,
    provider_models: [...providerModels].sort(),
    usage: totalUsage,
    known_cost_usd: knownCostUsd,
    priced_runs: pricedRuns,
    unpriced_runs: unpricedRuns,
    cost_complete: unpricedRuns === 0 && (state.runs?.length ?? 0) > 0,
  };
}

export class KairoJobUsageLedger {
  constructor({ dataDir, clock = () => new Date() }) {
    this.dataDir = path.resolve(requireText(dataDir, "dataDir"));
    this.clock = clock;
    this.store = new KairoStore({ dataDir: this.dataDir, clock });
  }

  async findJobBySchedulerId(schedulerId) {
    const id = requireText(schedulerId, "schedulerId");
    const matches = [];
    const projects = await this.store.listProjects();
    for (const project of projects) {
      const dir = path.join(this.dataDir, "projects", project.slug, "jobs");
      if (!(await exists(dir))) continue;
      const entries = await readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
        const jobId = entry.name.slice(0, -3);
        if (!jobId.startsWith("job_")) continue;
        const { metadata } = parseMarkdown(await readFile(path.join(dir, entry.name), "utf8"));
        if (metadata.type === "job" && metadata.scheduler_id === id) {
          matches.push({ project_slug: project.slug, job_id: jobId, scheduler_id: id });
        }
      }
    }
    if (matches.length > 1) {
      throw new KairoError("AMBIGUOUS_SCHEDULER_ID", `Scheduler '${id}' is linked to multiple KAIRO jobs.`);
    }
    return matches[0] ?? null;
  }

  async recordLlmOutputBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordLlmOutput(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordFinalSnapshotBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordFinalSnapshot(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordToolCallBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordToolCall(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordLlmOutput(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, {
      sessionId: input.sessionId,
      provider: input.provider,
      model: input.model,
      resolvedRef: input.resolvedRef,
      harnessId: input.harnessId,
    });
    const call = {
      sequence: run.calls.length + 1,
      captured_at: nowIso(this.clock),
      provider: requireText(input.provider, "provider"),
      model: requireText(input.model, "model"),
      usage: normalizeUsage(input.usage),
      ...(optionalText(input.resolvedRef) ? { resolved_ref: optionalText(input.resolvedRef) } : {}),
      ...(optionalText(input.harnessId) ? { harness_id: optionalText(input.harnessId) } : {}),
    };
    run.calls.push(call);
    run.aggregate = runAggregate(run.calls);
    run.updated_at = call.captured_at;
    state.updated_at = call.captured_at;
    await this.#write(state);
    return { state, summary: summarize(state), run, call };
  }

  async recordFinalSnapshot(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, {
      sessionId: input.sessionId,
      provider: input.provider,
      model: input.model,
      resolvedRef: input.resolvedRef,
    });
    const timestamp = nowIso(this.clock);
    const snapshot = {
      captured_at: timestamp,
      provider: optionalText(input.provider),
      model: optionalText(input.model),
      resolved_ref: optionalText(input.resolvedRef),
      usage: normalizeUsage(input.usage),
      turn_usd: normalizeCounter(input.turnUsd, "turnUsd"),
      duration_ms: normalizeCounter(input.durationMs, "durationMs"),
      fallback_used: input.fallbackUsed === undefined ? undefined : Boolean(input.fallbackUsed),
    };
    for (const key of Object.keys(snapshot)) if (snapshot[key] === undefined) delete snapshot[key];
    run.final_snapshot = snapshot;
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run };
  }

  async recordToolCall(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, {});
    const timestamp = nowIso(this.clock);
    run.tool_calls.push({
      sequence: run.tool_calls.length + 1,
      captured_at: timestamp,
      tool_name: requireText(input.toolName, "toolName"),
      outcome: input.error ? "error" : "success",
      ...(optionalText(input.error) ? { error: optionalText(input.error) } : {}),
      ...(normalizeCounter(input.durationMs, "durationMs") !== undefined
        ? { duration_ms: normalizeCounter(input.durationMs, "durationMs") }
        : {}),
    });
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run };
  }

  async getUsage(project, jobId) {
    const state = await this.#readOrCreate(project, jobId);
    return { state, summary: summarize(state) };
  }

  #run(state, runId, defaults) {
    const id = requireText(runId, "runId");
    let run = state.runs.find((item) => item.run_id === id);
    if (!run) {
      run = {
        run_id: id,
        created_at: nowIso(this.clock),
        updated_at: nowIso(this.clock),
        calls: [],
        tool_calls: [],
      };
      state.runs.push(run);
    }
    if (!run.session_id && optionalText(defaults.sessionId)) run.session_id = optionalText(defaults.sessionId);
    if (!run.provider && optionalText(defaults.provider)) run.provider = optionalText(defaults.provider);
    if (!run.model && optionalText(defaults.model)) run.model = optionalText(defaults.model);
    if (!run.resolved_ref && optionalText(defaults.resolvedRef)) run.resolved_ref = optionalText(defaults.resolvedRef);
    if (!run.harness_id && optionalText(defaults.harnessId)) run.harness_id = optionalText(defaults.harnessId);
    if (!Array.isArray(run.calls)) run.calls = [];
    if (!Array.isArray(run.tool_calls)) run.tool_calls = [];
    return run;
  }

  async #readOrCreate(project, jobId, schedulerId) {
    const projectRecord = await this.store.getProject(project);
    const safeJobId = assertSafeId(requireText(jobId, "jobId"), "jobId");
    if (!safeJobId.startsWith("job_")) throw new TypeError("Invalid jobId.");
    const source = jobFile(this.dataDir, projectRecord.slug, safeJobId);
    if (!(await exists(source))) {
      throw new KairoError("JOB_NOT_FOUND", `job '${safeJobId}' was not found in '${projectRecord.slug}'.`);
    }
    const { metadata } = parseMarkdown(await readFile(source, "utf8"));
    if (metadata.type !== "job") throw new KairoError("JOB_NOT_FOUND", `job '${safeJobId}' is invalid.`);
    const file = usageFile(this.dataDir, projectRecord.slug, safeJobId);
    if (await exists(file)) {
      const state = JSON.parse(await readFile(file, "utf8"));
      if (!Array.isArray(state.runs)) state.runs = [];
      return state;
    }
    const timestamp = nowIso(this.clock);
    return {
      type: "job_usage",
      job_id: safeJobId,
      project_slug: projectRecord.slug,
      scheduler_id: optionalText(schedulerId) ?? optionalText(metadata.scheduler_id),
      created_at: timestamp,
      updated_at: timestamp,
      runs: [],
    };
  }

  async #write(state) {
    await atomicWriteJson(usageFile(this.dataDir, state.project_slug, state.job_id), state);
  }
}
