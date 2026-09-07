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

function jobBody({ title, instructions, completionSummary, failureReason }) {
  const sections = [`# ${title}`, `## Instructions\n${instructions}`];
  if (completionSummary) sections.push(`## Completion summary\n${completionSummary}`);
  if (failureReason) sections.push(`## Failure\n${failureReason}`);
  return sections.join("\n\n");
}

function jobFile(dataDir, projectSlug, jobId) {
  return path.join(dataDir, "projects", projectSlug, "jobs", `${jobId}.md`);
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

  async completeJob(project, jobId, { summary }) {
    const completionSummary = requireText(summary, "Completion summary");
    return this.#transition(project, jobId, ["running", "queued"], "completed", {
      completed_at: nowIso(this.clock),
      completion_summary: completionSummary,
    });
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

  async #transition(project, jobId, allowedFrom, target, patch) {
    if (!JOB_STATUSES.has(target)) throw new TypeError(`Invalid job status: ${target}`);
    return this.#update(project, jobId, (job) => {
      if (!allowedFrom.includes(job.status)) {
        throw new KairoError(
          "INVALID_JOB_TRANSITION",
          `Cannot move job '${job.id}' from '${job.status}' to '${target}'.`,
        );
      }
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
