import { mkdir, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { createId, assertSafeId } from "./ids.js";
import { parseMarkdown, serializeMarkdown } from "./frontmatter.js";
import { KairoError } from "./errors.js";
import { KairoStore } from "./store.js";

const JOB_STATUSES = new Set([
  "scheduling",
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
]);
const JOB_STEP_STATUSES = new Set(["started", "completed"]);
const AUTHORITY_LEVELS = new Set(["A0", "A1", "A2", "A3", "A4", "A5"]);

function requireText(value, label) {
  const text = String(value ?? "").trim();
  if (!text) throw new TypeError(`${label} is required.`);
  return text;
}

function optionalText(value) {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function requireStepKey(value) {
  const key = requireText(value, "stepKey");
  if (!/^[a-z0-9][a-z0-9._:-]{0,127}$/i.test(key)) {
    throw new TypeError("stepKey must be 1-128 characters using letters, numbers, '.', '_', ':', or '-'.");
  }
  return key;
}

function nowIso(clock) {
  return clock().toISOString();
}

function optionalBudget(value) {
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    throw new TypeError("requestedBudget must be a non-negative number.");
  }
  return number;
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

async function atomicWrite(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const temp = `${filePath}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  await writeFile(temp, content, { encoding: "utf8", flag: "wx" });
  await rename(temp, filePath);
}

function oneLine(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function jobBody({ title, instructions, completionSummary, failureReason, executionSteps = [] }) {
  const sections = [`# ${title}`, `## Instructions\n${instructions}`];
  if (executionSteps.length) {
    sections.push(
      `## Execution checkpoints\n${executionSteps
        .map((step) => {
          const details = [
            `\`${step.key}\``,
            step.status,
            `started ${step.started_at}`,
            ...(step.completed_at ? [`completed ${step.completed_at}`] : []),
            ...(step.description ? [oneLine(step.description)] : []),
            ...(step.summary ? [oneLine(step.summary)] : []),
          ];
          return `- ${details.join(" — ")}`;
        })
        .join("\n")}`,
    );
  }
  if (completionSummary) sections.push(`## Completion summary\n${completionSummary}`);
  if (failureReason) sections.push(`## Failure\n${failureReason}`);
  return sections.join("\n\n");
}

function jobFile(dataDir, projectSlug, jobId) {
  return path.join(dataDir, "projects", projectSlug, "jobs", `${jobId}.md`);
}

function executionSteps(job) {
  const raw = job.execution_steps;
  if (raw === undefined) return [];
  if (!Array.isArray(raw)) {
    throw new KairoError("INVALID_JOB_STEPS", `Job '${job.id}' has invalid execution_steps metadata.`);
  }
  return raw.map((value) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new KairoError("INVALID_JOB_STEPS", `Job '${job.id}' has an invalid execution step.`);
    }
    const step = { ...value };
    step.key = requireStepKey(step.key);
    step.status = requireText(step.status, "Execution step status");
    if (!JOB_STEP_STATUSES.has(step.status)) {
      throw new KairoError(
        "INVALID_JOB_STEPS",
        `Job '${job.id}' has invalid execution step status '${step.status}'.`,
      );
    }
    step.started_at = requireText(step.started_at, "Execution step started_at");
    if (step.description !== undefined) step.description = requireText(step.description, "Execution step description");
    if (step.completed_at !== undefined) step.completed_at = requireText(step.completed_at, "Execution step completed_at");
    if (step.summary !== undefined) step.summary = requireText(step.summary, "Execution step summary");
    return step;
  });
}

function assertRunningStepJob(job) {
  if (job.status !== "running") {
    throw new KairoError(
      "INVALID_JOB_STEP_STATE",
      `Cannot modify execution checkpoints for job '${job.id}' while status is '${job.status}'.`,
    );
  }
}

/**
 * Durable execution ledger for KAIRO-owned work.
 *
 * This is intentionally separate from OpenClaw's scheduler/task storage: the
 * external runtime can be replaced while KAIRO keeps its audit trail.
 */
export class KairoJobLedger {
  constructor({ dataDir, clock = () => new Date() }) {
    this.dataDir = path.resolve(requireText(dataDir, "dataDir"));
    this.clock = clock;
    this.store = new KairoStore({ dataDir: this.dataDir, clock });
  }

  async createJob({
    project,
    title,
    instructions,
    authorityCeiling = "A2",
    scheduledFor,
    requestedBudget,
    sourceSession,
    taskId,
  }) {
    const projectRecord = await this.store.getProject(project);
    if (!AUTHORITY_LEVELS.has(authorityCeiling)) {
      throw new TypeError(`Invalid authority ceiling: ${authorityCeiling}`);
    }
    const normalizedTitle = requireText(title, "Job title");
    const normalizedInstructions = requireText(instructions, "Job instructions");
    const timestamp = nowIso(this.clock);
    const job = {
      id: createId("job"),
      type: "job",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      status: "scheduling",
      authority_ceiling: authorityCeiling,
      created_at: timestamp,
      updated_at: timestamp,
    };

    const normalizedScheduledFor = optionalText(scheduledFor);
    if (normalizedScheduledFor) job.scheduled_for = normalizedScheduledFor;
    const normalizedBudget = optionalBudget(requestedBudget);
    if (normalizedBudget !== undefined) {
      job.requested_budget = normalizedBudget;
      job.budget_enforced = false;
    }
    const normalizedSession = optionalText(sourceSession);
    if (normalizedSession) job.source_session = normalizedSession;
    if (taskId) job.task_id = assertSafeId(requireText(taskId, "taskId"), "taskId");

    await atomicWrite(
      jobFile(this.dataDir, projectRecord.slug, job.id),
      serializeMarkdown(job, jobBody({ title: normalizedTitle, instructions: normalizedInstructions })),
    );
    return { ...job, instructions: normalizedInstructions };
  }

  async linkScheduler(project, jobId, { schedulerId, schedulerTag, schedulerKind = "openclaw-session-turn" }) {
    return this.#update(project, jobId, (job) => ({
      ...job,
      status: "queued",
      scheduler_id: requireText(schedulerId, "schedulerId"),
      scheduler_tag: requireText(schedulerTag, "schedulerTag"),
      scheduler_kind: requireText(schedulerKind, "schedulerKind"),
      queued_at: nowIso(this.clock),
      updated_at: nowIso(this.clock),
    }));
  }

  async markRunning(project, jobId) {
    return this.#transition(project, jobId, ["queued", "scheduling"], "running", {
      started_at: nowIso(this.clock),
    });
  }

  async beginStep(project, jobId, { stepKey, description } = {}) {
    const key = requireStepKey(stepKey);
    const normalizedDescription = optionalText(description);
    let selectedStep;
    let disposition;

    const job = await this.#update(project, jobId, (current) => {
      assertRunningStepJob(current);
      const steps = executionSteps(current);
      const existing = steps.find((step) => step.key === key);
      if (existing) {
        selectedStep = { ...existing };
        disposition = existing.status === "completed" ? "already_completed" : "already_started";
        return current;
      }

      const timestamp = nowIso(this.clock);
      const step = {
        key,
        status: "started",
        started_at: timestamp,
        ...(normalizedDescription ? { description: normalizedDescription } : {}),
      };
      selectedStep = { ...step };
      disposition = "started";
      return {
        ...current,
        execution_steps: [...steps, step],
        updated_at: timestamp,
      };
    });

    return { job, step: selectedStep, disposition };
  }

  async completeStep(project, jobId, { stepKey, summary } = {}) {
    const key = requireStepKey(stepKey);
    const completionSummary = requireText(summary, "Execution step summary");
    let selectedStep;
    let disposition;

    const job = await this.#update(project, jobId, (current) => {
      assertRunningStepJob(current);
      const steps = executionSteps(current);
      const index = steps.findIndex((step) => step.key === key);
      if (index === -1) {
        throw new KairoError(
          "JOB_STEP_NOT_FOUND",
          `Execution step '${key}' was not started for job '${current.id}'.`,
        );
      }

      const existing = steps[index];
      if (existing.status === "completed") {
        selectedStep = { ...existing };
        disposition = "already_completed";
        return current;
      }

      const timestamp = nowIso(this.clock);
      const completed = {
        ...existing,
        status: "completed",
        completed_at: timestamp,
        summary: completionSummary,
      };
      const nextSteps = [...steps];
      nextSteps[index] = completed;
      selectedStep = { ...completed };
      disposition = "completed";
      return {
        ...current,
        execution_steps: nextSteps,
        updated_at: timestamp,
      };
    });

    return { job, step: selectedStep, disposition };
  }

  async completeJob(project, jobId, { summary }) {
    const completionSummary = requireText(summary, "Completion summary");
    return this.#transition(
      project,
      jobId,
      ["running", "queued"],
      "completed",
      {
        completed_at: nowIso(this.clock),
        completion_summary: completionSummary,
      },
      (job) => {
        const unresolved = executionSteps(job).filter((step) => step.status === "started");
        if (unresolved.length) {
          throw new KairoError(
            "UNRESOLVED_JOB_STEPS",
            `Cannot complete job '${job.id}' with unresolved execution steps: ${unresolved
              .map((step) => step.key)
              .join(", ")}.`,
          );
        }
      },
    );
  }

  async failJob(project, jobId, { reason }) {
    const failureReason = requireText(reason, "Failure reason");
    return this.#transition(project, jobId, ["scheduling", "queued", "running"], "failed", {
      failed_at: nowIso(this.clock),
      failure_reason: failureReason,
    });
  }

  async cancelJob(project, jobId, { reason } = {}) {
    return this.#transition(project, jobId, ["scheduling", "queued"], "cancelled", {
      cancelled_at: nowIso(this.clock),
      ...(optionalText(reason) ? { cancellation_reason: optionalText(reason) } : {}),
    });
  }

  async getJob(project, jobId) {
    const projectRecord = await this.store.getProject(project);
    const safeId = assertSafeId(requireText(jobId, "jobId"), "jobId");
    if (!safeId.startsWith("job_")) throw new TypeError("Invalid jobId.");
    const file = jobFile(this.dataDir, projectRecord.slug, safeId);
    if (!(await exists(file))) {
      throw new KairoError("JOB_NOT_FOUND", `job '${safeId}' was not found in '${projectRecord.slug}'.`);
    }
    const { metadata, body } = parseMarkdown(await readFile(file, "utf8"));
    return { ...metadata, body };
  }

  async listJobs(project) {
    const projectRecord = await this.store.getProject(project);
    const dir = path.join(this.dataDir, "projects", projectRecord.slug, "jobs");
    if (!(await exists(dir))) return [];
    const entries = await readdir(dir, { withFileTypes: true });
    const jobs = [];
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
      const id = entry.name.slice(0, -3);
      if (!id.startsWith("job_")) continue;
      jobs.push(await this.getJob(projectRecord.slug, id));
    }
    return jobs.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  }

  async #transition(project, jobId, allowedFrom, target, patch, validate) {
    if (!JOB_STATUSES.has(target)) throw new TypeError(`Invalid job status: ${target}`);
    return this.#update(project, jobId, (job) => {
      if (!allowedFrom.includes(job.status)) {
        throw new KairoError(
          "INVALID_JOB_TRANSITION",
          `Cannot move job '${job.id}' from '${job.status}' to '${target}'.`,
        );
      }
      validate?.(job);
      return {
        ...job,
        ...patch,
        status: target,
        updated_at: nowIso(this.clock),
      };
    });
  }

  async #update(project, jobId, mutate) {
    const current = await this.getJob(project, jobId);
    const next = mutate({ ...current });
    if (!JOB_STATUSES.has(next.status)) throw new TypeError(`Invalid job status: ${next.status}`);

    const projectRecord = await this.store.getProject(project);
    const instructions = extractSection(current.body, "Instructions") || "No instructions recorded.";
    const content = jobBody({
      title: next.title,
      instructions,
      completionSummary: next.completion_summary,
      failureReason: next.failure_reason,
      executionSteps: executionSteps(next),
    });
    const metadata = { ...next };
    delete metadata.body;
    await atomicWrite(jobFile(this.dataDir, projectRecord.slug, next.id), serializeMarkdown(metadata, content));
    return { ...metadata, body: content };
  }
}

function extractSection(body, heading) {
  const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = String(body ?? "").match(new RegExp(`(?:^|\\n)## ${escaped}\\n([\\s\\S]*?)(?=\\n## |$)`));
  return match?.[1]?.trim();
}
