import { mkdir, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { assertSafeId } from "./ids.js";
import { parseMarkdown } from "./frontmatter.js";
import { KairoError } from "./errors.js";
import { KairoStore } from "./store.js";

const JOB_USAGE_SCHEMA_VERSION = 3;

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

function hasUsage(usage) {
  return Boolean(usage && typeof usage === "object" && Object.keys(usage).length > 0);
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

function observedUsage(run) {
  const observations = Array.isArray(run.usage_observations) ? run.usage_observations : [];
  return observations.reduce((sum, observation) => addUsage(sum, observation.usage ?? {}), {});
}

function effectiveRunUsage(run) {
  const finalUsage = run.final_snapshot?.usage;
  if (hasUsage(finalUsage)) {
    return { usage: finalUsage, source: "final_snapshot", complete: true };
  }
  const usage = observedUsage(run);
  if (hasUsage(usage)) {
    return { usage, source: "llm_output_observed", complete: false };
  }
  return { usage: {}, source: "none", complete: false };
}

function addProviderModel(target, provider, model) {
  const normalizedProvider = optionalText(provider);
  const normalizedModel = optionalText(model);
  if (normalizedProvider && normalizedModel) target.add(`${normalizedProvider}/${normalizedModel}`);
}

function routeRef(provider, model) {
  const normalizedProvider = optionalText(provider);
  const normalizedModel = optionalText(model);
  return normalizedProvider && normalizedModel ? `${normalizedProvider}/${normalizedModel}` : undefined;
}

function uniqueTexts(values) {
  return [...new Set(values.map(optionalText).filter(Boolean))].sort();
}

function observedRouteRefs(run) {
  const refs = [];
  for (const call of run.model_calls ?? []) {
    const ref = routeRef(call.provider, call.model);
    if (ref) refs.push(ref);
  }
  for (const observation of run.usage_observations ?? []) {
    const ref = optionalText(observation.resolved_ref) ?? routeRef(observation.provider, observation.model);
    if (ref) refs.push(ref);
  }
  return uniqueTexts(refs);
}

function observedHarnessIds(run) {
  return uniqueTexts((run.usage_observations ?? []).map((observation) => observation.harness_id));
}

function routingEvidenceSources(run) {
  const sources = [];
  if (run.route_request) sources.push("before_agent_reply");
  if ((run.model_calls?.length ?? 0) > 0) sources.push("model_call");
  if ((run.usage_observations?.length ?? 0) > 0) sources.push("llm_output");
  if (run.final_snapshot) sources.push("final_snapshot");
  return uniqueTexts(sources);
}

function deriveRunRouting(run) {
  const finalSnapshot =
    run.final_snapshot && typeof run.final_snapshot === "object" && !Array.isArray(run.final_snapshot)
      ? run.final_snapshot
      : undefined;
  const observedRefs = observedRouteRefs(run);
  const harnessIds = observedHarnessIds(run);
  const requestedRef =
    optionalText(finalSnapshot?.requested) ?? optionalText(run.route_request?.requested_ref);
  const resolvedRef =
    optionalText(finalSnapshot?.resolved_ref) ?? (observedRefs.length === 1 ? observedRefs[0] : undefined);
  const fallbackUsed =
    typeof finalSnapshot?.fallback_used === "boolean" ? finalSnapshot.fallback_used : undefined;
  const overrideSource = optionalText(finalSnapshot?.override_source);
  const authMode = optionalText(finalSnapshot?.auth_mode);

  let classification;
  let reasonCode;
  let reason;
  let complete = false;

  if (fallbackUsed === true) {
    classification = "fallback";
    reasonCode = resolvedRef ? "fallback_used" : "fallback_without_resolved_winner";
    reason = resolvedRef
      ? `OpenClaw final routing snapshot reports fallback_used=true and resolved '${resolvedRef}'.`
      : "OpenClaw final routing snapshot reports fallback_used=true but no resolved winner was recorded.";
    complete = Boolean(requestedRef && resolvedRef);
  } else if (fallbackUsed === false && requestedRef && resolvedRef && overrideSource) {
    classification = "session_override";
    reasonCode = requestedRef === resolvedRef ? "session_override" : "session_override_resolved_difference";
    reason =
      requestedRef === resolvedRef
        ? `OpenClaw final routing snapshot reports model override source '${overrideSource}' and requested route equals resolved route.`
        : `OpenClaw final routing snapshot reports model override source '${overrideSource}', requested '${requestedRef}', and resolved '${resolvedRef}' without fallback.`;
    complete = true;
  } else if (fallbackUsed === false && requestedRef && resolvedRef && requestedRef === resolvedRef) {
    classification = "requested";
    reasonCode = "requested_equals_resolved";
    reason = "OpenClaw final routing snapshot reports the requested route was used without fallback.";
    complete = true;
  } else if (fallbackUsed === false && requestedRef && resolvedRef) {
    classification = "resolved_difference";
    reasonCode = "requested_resolved_mismatch_without_fallback";
    reason = `OpenClaw final routing snapshot requested '${requestedRef}' and resolved '${resolvedRef}' while fallback_used=false; KAIRO records the difference without inventing its cause.`;
    complete = true;
  } else if (finalSnapshot && resolvedRef) {
    classification = "final_snapshot_partial";
    reasonCode = "final_snapshot_missing_route_fields";
    reason = "OpenClaw produced a final routing snapshot, but it did not contain enough requested/fallback fields for a complete classification.";
  } else if (observedRefs.length > 1) {
    classification = "multiple_observed_routes";
    reasonCode = "multiple_routes_without_authoritative_winner";
    reason = "Multiple provider/model routes were observed, but no authoritative final routing snapshot identified the winner.";
  } else if (requestedRef && resolvedRef && requestedRef === resolvedRef) {
    classification = "observed_match";
    reasonCode = "final_snapshot_missing";
    reason = "The pre-run requested route matches the observed route, but no authoritative final routing snapshot was delivered.";
  } else if (requestedRef && resolvedRef) {
    classification = "observed_difference";
    reasonCode = "final_snapshot_missing";
    reason = `The pre-run requested route '${requestedRef}' differs from the observed route '${resolvedRef}', but no authoritative final routing snapshot was delivered.`;
  } else if (resolvedRef) {
    classification = "observed_only";
    reasonCode = "requested_or_final_snapshot_missing";
    reason = "An actual provider/model route was observed, but requested-route/fallback provenance is incomplete.";
  } else if (requestedRef) {
    classification = "requested_only";
    reasonCode = "resolved_route_missing";
    reason = "A pre-run requested route was recorded, but no model route observation was captured.";
  } else {
    classification = "unknown";
    reasonCode = "route_not_observed";
    reason = "No trustworthy routing evidence was captured for this run.";
  }

  return {
    run_id: requireText(run.run_id, "runId"),
    classification,
    reason_code: reasonCode,
    reason,
    complete,
    ...(requestedRef ? { requested_ref: requestedRef } : {}),
    ...(resolvedRef ? { resolved_ref: resolvedRef } : {}),
    ...(fallbackUsed !== undefined ? { fallback_used: fallbackUsed } : {}),
    ...(overrideSource ? { override_source: overrideSource } : {}),
    ...(authMode ? { auth_mode: authMode } : {}),
    harness_ids: harnessIds,
    observed_refs: observedRefs,
    evidence_sources: routingEvidenceSources(run),
  };
}

function runHasModelActivity(run) {
  if ((run.model_calls?.length ?? 0) > 0) return true;
  if ((run.usage_observations?.length ?? 0) > 0) return true;
  if (hasUsage(run.final_snapshot?.usage)) return true;
  return Boolean(run.final_snapshot?.provider && run.final_snapshot?.model);
}

function summarize(state) {
  const totalUsage = {};
  const providerModels = new Set();
  const harnesses = new Set();
  const usageSources = new Set();
  let knownCostUsd = 0;
  let pricedRuns = 0;
  let unpricedRuns = 0;
  let modelCalls = 0;
  let usageObservations = 0;
  let toolCalls = 0;
  let usageComplete = (state.runs?.length ?? 0) > 0;

  for (const run of state.runs ?? []) {
    const effective = effectiveRunUsage(run);
    Object.assign(totalUsage, addUsage(totalUsage, effective.usage));
    usageSources.add(effective.source);
    if (!effective.complete && runHasModelActivity(run)) usageComplete = false;

    for (const call of run.model_calls ?? []) addProviderModel(providerModels, call.provider, call.model);
    for (const observation of run.usage_observations ?? []) {
      addProviderModel(providerModels, observation.provider, observation.model);
      const harnessId = optionalText(observation.harness_id);
      if (harnessId) harnesses.add(harnessId);
    }
    addProviderModel(providerModels, run.final_snapshot?.provider, run.final_snapshot?.model);

    modelCalls += Array.isArray(run.model_calls) ? run.model_calls.length : 0;
    usageObservations += Array.isArray(run.usage_observations) ? run.usage_observations.length : 0;
    toolCalls += Array.isArray(run.tool_calls) ? run.tool_calls.length : 0;

    if (runHasModelActivity(run)) {
      if (run.final_snapshot && Number.isFinite(run.final_snapshot.turn_usd)) {
        knownCostUsd += run.final_snapshot.turn_usd;
        pricedRuns += 1;
      } else {
        unpricedRuns += 1;
      }
    }
  }

  if ((state.runs?.length ?? 0) === 0) usageComplete = false;
  const routing = (state.runs ?? []).filter(runHasModelActivity).map(deriveRunRouting);

  return {
    schema_version: JOB_USAGE_SCHEMA_VERSION,
    runs: state.runs?.length ?? 0,
    model_calls: modelCalls,
    usage_observations: usageObservations,
    tool_calls: toolCalls,
    provider_models: [...providerModels].sort(),
    harnesses: [...harnesses].sort(),
    usage: totalUsage,
    usage_sources: [...usageSources].sort(),
    usage_complete: usageComplete,
    known_cost_usd: knownCostUsd,
    priced_runs: pricedRuns,
    unpriced_runs: unpricedRuns,
    cost_complete: unpricedRuns === 0 && pricedRuns > 0,
    routing,
    routing_complete: routing.length > 0 && routing.every((route) => route.complete),
  };
}

function normalizeExistingState(state) {
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    throw new KairoError("INVALID_JOB_USAGE", "Job usage state must be an object.");
  }
  state.runs = Array.isArray(state.runs) ? state.runs : [];
  for (const run of state.runs) {
    if (!run || typeof run !== "object" || Array.isArray(run)) continue;
    const legacyCalls = Array.isArray(run.calls) ? run.calls : [];
    if (!Array.isArray(run.model_calls)) run.model_calls = [];
    if (!Array.isArray(run.usage_observations)) {
      run.usage_observations = legacyCalls.map((call, index) => ({
        sequence: index + 1,
        captured_at: call.captured_at ?? run.updated_at ?? state.updated_at,
        provider: call.provider,
        model: call.model,
        ...(call.resolved_ref ? { resolved_ref: call.resolved_ref } : {}),
        ...(call.harness_id ? { harness_id: call.harness_id } : {}),
        usage: call.usage ?? {},
        source: "legacy_llm_output",
      }));
    }
    if (!Array.isArray(run.tool_calls)) run.tool_calls = [];
    delete run.calls;
    delete run.aggregate;
  }
  state.schema_version = JOB_USAGE_SCHEMA_VERSION;
  return state;
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

  async recordRunBindingBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordRunBinding(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordRouteRequestBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordRouteRequest(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordModelCallStartedBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordModelCallStarted(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordModelCallEndedBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordModelCallEnded(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordUsageObservationBySchedulerId(schedulerId, input) {
    const match = await this.findJobBySchedulerId(schedulerId);
    if (!match) return null;
    return this.recordUsageObservation(match.project_slug, match.job_id, { ...input, schedulerId });
  }

  async recordLlmOutputBySchedulerId(schedulerId, input) {
    return this.recordUsageObservationBySchedulerId(schedulerId, input);
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

  async recordRunBinding(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
    const timestamp = nowIso(this.clock);
    if (!run.bound_at) run.bound_at = timestamp;
    if (!run.trigger && optionalText(input.trigger)) run.trigger = optionalText(input.trigger);
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run };
  }

  async recordRouteRequest(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
    if (run.route_request) {
      return {
        state,
        summary: summarize(state),
        run,
        routeRequest: run.route_request,
        disposition: "already_observed",
      };
    }

    const provider = optionalText(input.provider);
    const model = optionalText(input.model);
    if (!provider && !model) {
      return { state, summary: summarize(state), run, disposition: "ignored" };
    }

    const timestamp = nowIso(this.clock);
    const requestedRef = routeRef(provider, model);
    const routeRequest = {
      captured_at: timestamp,
      source: "before_agent_reply",
      ...(provider ? { provider } : {}),
      ...(model ? { model } : {}),
      ...(requestedRef ? { requested_ref: requestedRef } : {}),
    };
    run.route_request = routeRequest;
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run, routeRequest, disposition: "observed" };
  }

  async recordModelCallStarted(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
    const callId = requireText(input.callId, "callId");
    const existing = run.model_calls.find((item) => item.call_id === callId);
    if (existing) return { state, summary: summarize(state), run, call: existing, disposition: "already_observed" };

    const timestamp = nowIso(this.clock);
    const call = {
      call_id: callId,
      started_at: timestamp,
      provider: requireText(input.provider, "provider"),
      model: requireText(input.model, "model"),
      ...(optionalText(input.api) ? { api: optionalText(input.api) } : {}),
      ...(optionalText(input.transport) ? { transport: optionalText(input.transport) } : {}),
      ...(normalizeCounter(input.contextTokenBudget, "contextTokenBudget") !== undefined
        ? { context_token_budget: normalizeCounter(input.contextTokenBudget, "contextTokenBudget") }
        : {}),
    };
    run.model_calls.push(call);
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run, call, disposition: "started" };
  }

  async recordModelCallEnded(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
    const callId = requireText(input.callId, "callId");
    let call = run.model_calls.find((item) => item.call_id === callId);
    if (call?.ended_at) return { state, summary: summarize(state), run, call, disposition: "already_ended" };

    const timestamp = nowIso(this.clock);
    if (!call) {
      call = {
        call_id: callId,
        provider: requireText(input.provider, "provider"),
        model: requireText(input.model, "model"),
      };
      run.model_calls.push(call);
    }
    if (!call.provider) call.provider = requireText(input.provider, "provider");
    if (!call.model) call.model = requireText(input.model, "model");
    if (!call.api && optionalText(input.api)) call.api = optionalText(input.api);
    if (!call.transport && optionalText(input.transport)) call.transport = optionalText(input.transport);
    call.ended_at = timestamp;
    call.outcome = input.outcome === "error" ? "error" : "completed";
    const durationMs = normalizeCounter(input.durationMs, "durationMs");
    if (durationMs !== undefined) call.duration_ms = durationMs;
    if (optionalText(input.errorCategory)) call.error_category = optionalText(input.errorCategory);
    if (optionalText(input.failureKind)) call.failure_kind = optionalText(input.failureKind);
    if (optionalText(input.upstreamRequestIdHash)) call.upstream_request_id_hash = optionalText(input.upstreamRequestIdHash);
    for (const [inputKey, outputKey] of [
      ["requestPayloadBytes", "request_payload_bytes"],
      ["responseStreamBytes", "response_stream_bytes"],
      ["timeToFirstByteMs", "time_to_first_byte_ms"],
    ]) {
      const value = normalizeCounter(input[inputKey], inputKey);
      if (value !== undefined) call[outputKey] = value;
    }
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run, call, disposition: "ended" };
  }

  async recordUsageObservation(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
    const timestamp = nowIso(this.clock);
    const observation = {
      sequence: run.usage_observations.length + 1,
      captured_at: timestamp,
      source: "llm_output",
      provider: requireText(input.provider, "provider"),
      model: requireText(input.model, "model"),
      usage: normalizeUsage(input.usage),
      ...(optionalText(input.resolvedRef) ? { resolved_ref: optionalText(input.resolvedRef) } : {}),
      ...(optionalText(input.harnessId) ? { harness_id: optionalText(input.harnessId) } : {}),
      ...(normalizeCounter(input.contextTokenBudget, "contextTokenBudget") !== undefined
        ? { context_token_budget: normalizeCounter(input.contextTokenBudget, "contextTokenBudget") }
        : {}),
    };
    run.usage_observations.push(observation);
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run, observation };
  }

  async recordLlmOutput(project, jobId, input) {
    return this.recordUsageObservation(project, jobId, input);
  }

  async recordFinalSnapshot(project, jobId, input) {
    const state = await this.#readOrCreate(project, jobId, input.schedulerId);
    const run = this.#run(state, input.runId, { sessionId: input.sessionId });
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
      requested: optionalText(input.requested),
      override_source: optionalText(input.overrideSource),
      auth_mode: optionalText(input.authMode),
      reasoning_effort: optionalText(input.reasoningEffort),
      fast_mode: input.fastMode === undefined ? undefined : Boolean(input.fastMode),
      context_token_budget: normalizeCounter(input.contextTokenBudget, "contextTokenBudget"),
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
    const toolCallId = optionalText(input.toolCallId);
    if (toolCallId) {
      const existing = run.tool_calls.find((item) => item.tool_call_id === toolCallId);
      if (existing) return { state, summary: summarize(state), run, toolCall: existing, disposition: "already_observed" };
    }

    const timestamp = nowIso(this.clock);
    const toolCall = {
      sequence: run.tool_calls.length + 1,
      captured_at: timestamp,
      ...(toolCallId ? { tool_call_id: toolCallId } : {}),
      tool_name: requireText(input.toolName, "toolName"),
      outcome: input.error ? "error" : "success",
      ...(optionalText(input.error) ? { error: optionalText(input.error) } : {}),
      ...(normalizeCounter(input.durationMs, "durationMs") !== undefined
        ? { duration_ms: normalizeCounter(input.durationMs, "durationMs") }
        : {}),
    };
    run.tool_calls.push(toolCall);
    run.updated_at = timestamp;
    state.updated_at = timestamp;
    await this.#write(state);
    return { state, summary: summarize(state), run, toolCall, disposition: "observed" };
  }

  async getUsage(project, jobId) {
    const state = await this.#readOrCreate(project, jobId);
    return { state, summary: summarize(state) };
  }

  #run(state, runId, defaults) {
    const id = requireText(runId, "runId");
    let run = state.runs.find((item) => item.run_id === id);
    if (!run) {
      const timestamp = nowIso(this.clock);
      run = {
        run_id: id,
        created_at: timestamp,
        updated_at: timestamp,
        model_calls: [],
        usage_observations: [],
        tool_calls: [],
      };
      state.runs.push(run);
    }
    if (!run.session_id && optionalText(defaults.sessionId)) run.session_id = optionalText(defaults.sessionId);
    if (!Array.isArray(run.model_calls)) run.model_calls = [];
    if (!Array.isArray(run.usage_observations)) run.usage_observations = [];
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
      return normalizeExistingState(JSON.parse(await readFile(file, "utf8")));
    }
    const timestamp = nowIso(this.clock);
    return {
      schema_version: JOB_USAGE_SCHEMA_VERSION,
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
    state.schema_version = JOB_USAGE_SCHEMA_VERSION;
    await atomicWriteJson(usageFile(this.dataDir, state.project_slug, state.job_id), state);
  }
}
