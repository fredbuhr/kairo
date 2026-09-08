import { randomUUID } from "node:crypto";
import path from "node:path";
import { KairoJobLedger, KairoStore, type KairoRecord } from "@kairo/core";
import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";
import { jsonResult } from "openclaw/plugin-sdk/tool-results";

const projectStatus = Type.Union([
  Type.Literal("inbox"),
  Type.Literal("incubation"),
  Type.Literal("active"),
  Type.Literal("waiting"),
  Type.Literal("paused"),
  Type.Literal("completed"),
  Type.Literal("archived"),
]);

const epistemicStatus = Type.Union([
  Type.Literal("fact"),
  Type.Literal("hypothesis"),
  Type.Literal("deduction"),
  Type.Literal("opinion"),
  Type.Literal("unknown"),
]);

const sourceKind = Type.Union([
  Type.Literal("url"),
  Type.Literal("document"),
  Type.Literal("dataset"),
  Type.Literal("conversation"),
  Type.Literal("note"),
  Type.Literal("other"),
]);

const backgroundAuthority = Type.Union([
  Type.Literal("A0"),
  Type.Literal("A1"),
  Type.Literal("A2"),
]);

const BACKGROUND_JOB_LIFECYCLE_TOOLS = [
  "kairo_job_start",
  "kairo_job_get",
  "kairo_job_step_begin",
  "kairo_job_step_complete",
  "kairo_job_complete",
  "kairo_job_fail",
] as const;

const DEFAULT_BACKGROUND_TASK_TOOLS = [
  "kairo_project_list",
  "kairo_project_get",
  "kairo_idea_list",
  "kairo_idea_get",
  "kairo_source_get",
  "kairo_knowledge_get",
  "kairo_job_list",
] as const;

const configSchema = Type.Object(
  {
    dataDir: Type.String({
      minLength: 1,
      description: "Absolute path to KAIRO runtime-private domain data.",
    }),
  },
  { additionalProperties: false },
);

const backgroundScheduleParameters = Type.Object(
  {
    project: Type.String({ minLength: 1, description: "Existing KAIRO project slug or name." }),
    title: Type.String({ minLength: 1, description: "Concise background-work title." }),
    instructions: Type.String({ minLength: 1, description: "Work to perform during the future agent turn." }),
    at: Type.String({
      minLength: 1,
      description: "Absolute ISO-8601 date/time including Z or an explicit UTC offset, for example 2026-09-08T03:00:00+02:00.",
    }),
    authorityCeiling: Type.Optional(backgroundAuthority),
    requestedBudgetUsd: Type.Optional(
      Type.Number({
        minimum: 0,
        description: "Advisory requested model-spend budget in USD. Recorded durably but not hard-enforced until Gate 4 proves a pre-call enforcement seam.",
      }),
    ),
    requestedBudget: Type.Optional(
      Type.Number({
        minimum: 0,
        description: "Deprecated alias for requestedBudgetUsd. Legacy values are interpreted as USD.",
      }),
    ),
    allowedTools: Type.Optional(
      Type.Array(
        Type.String({
          minLength: 1,
          maxLength: 128,
          description: "Exact additional tool name allowed for the future turn. Wildcards and tool groups are rejected. KAIRO lifecycle tools are added automatically.",
        }),
        {
          description: "Exact additional task-tool allow-list. When omitted, KAIRO applies a conservative read-only KAIRO default. External, shell, browser, messaging, and web tools require explicit inclusion.",
        },
      ),
    ),
    announce: Type.Optional(
      Type.Boolean({ description: "When true (default), announce the result back to the session route after the scheduled turn." }),
    ),
  },
  { additionalProperties: false },
);

function assertAbsoluteDataDir(dataDir: string): string {
  if (!path.isAbsolute(dataDir)) {
    throw new Error("KAIRO plugin dataDir must be an absolute path.");
  }
  return dataDir;
}

export function storeFor(dataDir: string): KairoStore {
  return new KairoStore({ dataDir: assertAbsoluteDataDir(dataDir) });
}

export function ledgerFor(dataDir: string): KairoJobLedger {
  return new KairoJobLedger({ dataDir: assertAbsoluteDataDir(dataDir) });
}

function compact(record: KairoRecord): Record<string, unknown> {
  const { body: _body, ...metadata } = record;
  return metadata;
}

function parseAbsoluteSchedule(value: string): Date {
  const text = value.trim();
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(text)) {
    throw new TypeError("Background schedule must include Z or an explicit UTC offset.");
  }
  const timestamp = Date.parse(text);
  if (!Number.isFinite(timestamp)) throw new TypeError("Background schedule is not a valid ISO-8601 date/time.");
  return new Date(timestamp);
}

function resolveRequestedBudgetUsd(params: {
  requestedBudgetUsd?: number;
  requestedBudget?: number;
}): number | undefined {
  if (
    params.requestedBudgetUsd !== undefined &&
    params.requestedBudget !== undefined &&
    params.requestedBudgetUsd !== params.requestedBudget
  ) {
    throw new TypeError("requestedBudgetUsd and legacy requestedBudget must match when both are provided.");
  }
  return params.requestedBudgetUsd ?? params.requestedBudget;
}

function normalizeExactToolNames(values: readonly string[], label: string): string[] {
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const name = String(raw ?? "").trim();
    if (
      !name ||
      !/^[a-z0-9][a-z0-9_.:-]{0,127}$/i.test(name) ||
      name.toLowerCase().startsWith("group:") ||
      /[*?\[\]{}]/.test(name)
    ) {
      throw new TypeError(`${label} entries must be exact tool names, not groups or wildcard patterns.`);
    }
    const identity = name.toLowerCase();
    if (seen.has(identity)) continue;
    seen.add(identity);
    normalized.push(name);
  }
  return normalized;
}

function backgroundAllowedTools(requested?: string[]): {
  tools: string[];
  source: "default" | "explicit";
} {
  const taskTools = normalizeExactToolNames(
    requested ?? DEFAULT_BACKGROUND_TASK_TOOLS,
    "allowedTools",
  );
  return {
    tools: normalizeExactToolNames([...BACKGROUND_JOB_LIFECYCLE_TOOLS, ...taskTools], "allowedTools"),
    source: requested === undefined ? "default" : "explicit",
  };
}

function backgroundPrompt(params: {
  project: string;
  jobId: string;
  title: string;
  instructions: string;
  authorityCeiling: "A0" | "A1" | "A2";
  requestedBudgetUsd?: number;
  allowedTools: string[];
}): string {
  return [
    "[KAIRO BACKGROUND WORK]",
    `Project: ${params.project}`,
    `KAIRO job: ${params.jobId}`,
    `Title: ${params.title}`,
    `Authority ceiling: ${params.authorityCeiling}`,
    ...(params.requestedBudgetUsd !== undefined
      ? [`Requested model budget (USD): ${params.requestedBudgetUsd} (advisory; not yet hard-enforced)`]
      : []),
    `Allowed tools (runtime-enforced): ${params.allowedTools.join(", ")}`,
    "",
    "Task:",
    params.instructions,
    "",
    "Operating rules:",
    `1. Call kairo_job_start for project '${params.project}' and job '${params.jobId}' before beginning substantive work.`,
    "2. Use only the runtime-enforced allowed tools listed above. If a required tool is absent, do not work around the cap; fail the Job with the missing capability stated explicitly.",
    "3. Re-read the relevant KAIRO project context before acting.",
    "4. Keep facts, hypotheses, deductions, opinions, and unknowns distinct.",
    "5. Never exceed the stated authority ceiling. This V0 background scheduler never grants A3+ external authority.",
    "6. Do not publish, send messages, purchase, trade, delete external data, or change external systems.",
    "7. Before any replay-sensitive internal mutation, call kairo_job_step_begin with a stable stepKey that identifies that exact mutation.",
    "8. If kairo_job_step_begin returns already_completed, skip the mutation. If it returns already_started, the previous outcome is unknown: do not repeat the mutation blindly. Verify its effect deterministically when possible; otherwise stop and fail the Job with the uncertainty stated explicitly.",
    "9. After a replay-sensitive mutation is confirmed successful, call kairo_job_step_complete with the same stepKey and a concise factual summary.",
    "10. Pure reads and replay-safe deterministic computation do not require execution checkpoints.",
    "11. Persist evidence or knowledge only when the corresponding capture tool is present in the allowed-tools list and the task actually requires that write.",
    `12. On successful completion, call kairo_job_complete for job '${params.jobId}' with a concise factual summary. Job completion will be rejected while a started checkpoint remains unresolved.`,
    `13. If the work cannot complete, call kairo_job_fail for job '${params.jobId}' with the specific reason when possible.`,
    "14. If the task requires missing information or additional authority, stop and state the limitation explicitly.",
    "15. Return a concise completion report to the originating session when finished.",
  ].join("\n");
}

export default defineToolPlugin({
  id: "kairo-tools",
  name: "KAIRO Tools",
  description: "Durable KAIRO project, knowledge, job-ledger, and bounded background-work tools.",
  configSchema,
  tools: (tool) => [
    tool({
      name: "kairo_project_create",
      label: "Create KAIRO Project",
      description:
        "Create a durable KAIRO project. Use only when the user intends to create a project/domain container; do not create a new project merely because an idea mentions a new topic.",
      parameters: Type.Object(
        {
          name: Type.String({ minLength: 1, description: "Human-readable project name." }),
          slug: Type.Optional(
            Type.String({ minLength: 1, description: "Optional stable project slug. KAIRO can derive it from the name." }),
          ),
          summary: Type.Optional(Type.String({ description: "Short factual project summary." })),
          status: Type.Optional(projectStatus),
          parent: Type.Optional(
            Type.String({ minLength: 1, description: "Optional existing parent project slug/name." }),
          ),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const project = await storeFor(config.dataDir).createProject(params);
        return { project: compact(project) };
      },
    }),
    tool({
      name: "kairo_project_list",
      label: "List KAIRO Projects",
      description:
        "List durable KAIRO projects with compact metadata. Use this to resolve the correct project before writing project-scoped knowledge.",
      parameters: Type.Object({}, { additionalProperties: false }),
      async execute(_params, config, context) {
        context.signal?.throwIfAborted();
        const projects = await storeFor(config.dataDir).listProjects();
        return { projects: projects.map(compact) };
      },
    }),
    tool({
      name: "kairo_project_get",
      label: "Get KAIRO Project",
      description: "Read one KAIRO project, including its human-readable Markdown body.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1, description: "Project slug or name." }) },
        { additionalProperties: false },
      ),
      async execute({ project }, config, context) {
        context.signal?.throwIfAborted();
        return { project: await storeFor(config.dataDir).getProject(project) };
      },
    }),
    tool({
      name: "kairo_idea_capture",
      label: "Capture KAIRO Idea",
      description:
        "Persist an idea under an existing project. An idea is not a decision. Preserve uncertainty and the user's original wording when it matters; never promote a tentative statement to fact or decision.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Existing project slug or name." }),
          title: Type.String({ minLength: 1, description: "Concise idea title." }),
          content: Type.String({ minLength: 1, description: "Faithful description of the idea." }),
          rationale: Type.Optional(Type.String({ description: "Why the idea may be useful or relevant, if stated." })),
          epistemicStatus: Type.Optional(epistemicStatus),
          originalText: Type.Optional(
            Type.String({ description: "Exact user wording when available. Do not fabricate a quote." }),
          ),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const idea = await storeFor(config.dataDir).captureIdea({ ...params, sourceKind: "openclaw" });
        return { idea: compact(idea) };
      },
    }),
    tool({
      name: "kairo_idea_list",
      label: "List KAIRO Ideas",
      description: "List ideas belonging to one KAIRO project without importing ideas from unrelated projects.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1, description: "Project slug or name." }) },
        { additionalProperties: false },
      ),
      async execute({ project }, config, context) {
        context.signal?.throwIfAborted();
        const ideas = await storeFor(config.dataDir).listIdeas(project);
        return { ideas: ideas.map(compact) };
      },
    }),
    tool({
      name: "kairo_idea_get",
      label: "Get KAIRO Idea",
      description: "Read one durable idea, including its human-readable Markdown content and provenance metadata.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Project slug or name." }),
          ideaId: Type.String({ minLength: 1, description: "Stable KAIRO idea ID." }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, ideaId }, config, context) {
        context.signal?.throwIfAborted();
        return { idea: await storeFor(config.dataDir).getIdea(project, ideaId) };
      },
    }),
    tool({
      name: "kairo_source_capture",
      label: "Capture KAIRO Source",
      description:
        "Persist a source/evidence reference under an existing project. Store the locator faithfully; do not invent a source or claim that a source supports more than it actually does.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          title: Type.String({ minLength: 1 }),
          kind: sourceKind,
          locator: Type.String({ minLength: 1, description: "URL, document identifier/path, dataset locator, or other faithful source locator." }),
          summary: Type.Optional(Type.String({ description: "Short source summary grounded in the source." })),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const source = await storeFor(config.dataDir).captureSource(params);
        return { source: compact(source) };
      },
    }),
    tool({
      name: "kairo_source_get",
      label: "Get KAIRO Source",
      description: "Read one durable project source/evidence record.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1 }), sourceId: Type.String({ minLength: 1 }) },
        { additionalProperties: false },
      ),
      async execute({ project, sourceId }, config, context) {
        context.signal?.throwIfAborted();
        return { source: await storeFor(config.dataDir).getSource(project, sourceId) };
      },
    }),
    tool({
      name: "kairo_knowledge_capture",
      label: "Capture KAIRO Knowledge",
      description:
        "Persist one discrete knowledge claim with an explicit epistemic status. Use fact only when reliable available evidence supports the claim; otherwise choose hypothesis, deduction, opinion, or unknown.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          title: Type.String({ minLength: 1 }),
          claim: Type.String({ minLength: 1 }),
          epistemicStatus,
          confidence: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
          notes: Type.Optional(Type.String()),
          sourceIds: Type.Optional(Type.Array(Type.String({ minLength: 1 }))),
          lastVerifiedAt: Type.Optional(Type.String()),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const claim = await storeFor(config.dataDir).captureKnowledgeClaim(params);
        return { claim: compact(claim) };
      },
    }),
    tool({
      name: "kairo_knowledge_get",
      label: "Get KAIRO Knowledge",
      description: "Read one durable knowledge claim, including epistemic/provenance metadata and its Markdown body.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1 }), claimId: Type.String({ minLength: 1 }) },
        { additionalProperties: false },
      ),
      async execute({ project, claimId }, config, context) {
        context.signal?.throwIfAborted();
        return { claim: await storeFor(config.dataDir).getKnowledgeClaim(project, claimId) };
      },
    }),
    tool({
      name: "kairo_job_list",
      label: "List KAIRO Jobs",
      description: "List durable KAIRO execution jobs for one project, including scheduler linkage and lifecycle state.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1 }) },
        { additionalProperties: false },
      ),
      async execute({ project }, config, context) {
        context.signal?.throwIfAborted();
        const jobs = await ledgerFor(config.dataDir).listJobs(project);
        return { jobs: jobs.map(compact) };
      },
    }),
    tool({
      name: "kairo_job_get",
      label: "Get KAIRO Job",
      description: "Read one durable KAIRO job record with its instructions, status, scheduler linkage, execution checkpoints, and outcome.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1 }), jobId: Type.String({ minLength: 1 }) },
        { additionalProperties: false },
      ),
      async execute({ project, jobId }, config, context) {
        context.signal?.throwIfAborted();
        return { job: await ledgerFor(config.dataDir).getJob(project, jobId) };
      },
    }),
    tool({
      name: "kairo_job_start",
      label: "Start KAIRO Job",
      description: "Mark a queued KAIRO job as running. Use at the beginning of the scheduled KAIRO work turn.",
      parameters: Type.Object(
        { project: Type.String({ minLength: 1 }), jobId: Type.String({ minLength: 1 }) },
        { additionalProperties: false },
      ),
      async execute({ project, jobId }, config, context) {
        context.signal?.throwIfAborted();
        const job = await ledgerFor(config.dataDir).markRunning(project, jobId);
        return { job: compact(job) };
      },
    }),
    tool({
      name: "kairo_job_step_begin",
      label: "Begin KAIRO Job Step",
      description:
        "Persist a replay-safety checkpoint immediately before a replay-sensitive internal mutation. Reuse the same stable stepKey on retries. If disposition is already_started, the previous mutation outcome is unknown: do not repeat it blindly. If disposition is already_completed, skip the mutation.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          jobId: Type.String({ minLength: 1 }),
          stepKey: Type.String({
            minLength: 1,
            maxLength: 128,
            description: "Stable key for one exact replay-sensitive mutation, reused across retries.",
          }),
          description: Type.Optional(
            Type.String({ description: "Concise description of the mutation guarded by this checkpoint." }),
          ),
        },
        { additionalProperties: false },
      ),
      async execute({ project, jobId, stepKey, description }, config, context) {
        context.signal?.throwIfAborted();
        const result = await ledgerFor(config.dataDir).beginStep(project, jobId, { stepKey, description });
        return {
          job: compact(result.job),
          step: result.step,
          disposition: result.disposition,
        };
      },
    }),
    tool({
      name: "kairo_job_step_complete",
      label: "Complete KAIRO Job Step",
      description:
        "Mark a replay-safety checkpoint completed only after the guarded mutation is confirmed successful. Reuse the exact stepKey from kairo_job_step_begin. Repeated completion is idempotent.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          jobId: Type.String({ minLength: 1 }),
          stepKey: Type.String({ minLength: 1, maxLength: 128 }),
          summary: Type.String({ minLength: 1, description: "Concise factual confirmation of the mutation outcome." }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, jobId, stepKey, summary }, config, context) {
        context.signal?.throwIfAborted();
        const result = await ledgerFor(config.dataDir).completeStep(project, jobId, { stepKey, summary });
        return {
          job: compact(result.job),
          step: result.step,
          disposition: result.disposition,
        };
      },
    }),
    tool({
      name: "kairo_job_complete",
      label: "Complete KAIRO Job",
      description:
        "Mark a KAIRO job completed and persist a concise factual completion summary. Completion is rejected while any replay-safety checkpoint remains started and unresolved.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          jobId: Type.String({ minLength: 1 }),
          summary: Type.String({ minLength: 1 }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, jobId, summary }, config, context) {
        context.signal?.throwIfAborted();
        const job = await ledgerFor(config.dataDir).completeJob(project, jobId, { summary });
        return { job: compact(job) };
      },
    }),
    tool({
      name: "kairo_job_fail",
      label: "Fail KAIRO Job",
      description: "Mark a KAIRO job failed and persist the specific reason. Do not use failure to hide uncertainty; explain the actual blocker.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          jobId: Type.String({ minLength: 1 }),
          reason: Type.String({ minLength: 1 }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, jobId, reason }, config, context) {
        context.signal?.throwIfAborted();
        const job = await ledgerFor(config.dataDir).failJob(project, jobId, { reason });
        return { job: compact(job) };
      },
    }),
    tool({
      name: "kairo_background_schedule",
      label: "Schedule KAIRO Background Work",
      description:
        "Create a durable KAIRO job and schedule one bounded future agent turn in the current OpenClaw session. V0 is limited to A0-A2 internal/research work and enforces a per-job exact tool cap.",
      parameters: backgroundScheduleParameters,
      factory({ api, config, toolContext }) {
        const sessionKey = toolContext.sessionKey;
        if (!sessionKey) return null;
        return {
          name: "kairo_background_schedule",
          label: "Schedule KAIRO Background Work",
          description:
            "Create a durable KAIRO job and schedule one bounded future agent turn. V0 never grants A3+ external authority and enforces the durable allowed-tools cap in OpenClaw Cron.",
          parameters: backgroundScheduleParameters,
          async execute(_toolCallId, rawParams, signal) {
            signal?.throwIfAborted();
            const params = rawParams as {
              project: string;
              title: string;
              instructions: string;
              at: string;
              authorityCeiling?: "A0" | "A1" | "A2";
              requestedBudgetUsd?: number;
              requestedBudget?: number;
              allowedTools?: string[];
              announce?: boolean;
            };
            const store = storeFor(config.dataDir);
            const ledger = ledgerFor(config.dataDir);
            const project = await store.getProject(params.project);
            const at = parseAbsoluteSchedule(params.at);
            const authorityCeiling = params.authorityCeiling ?? "A2";
            const budgetUsd = resolveRequestedBudgetUsd(params);
            const toolCap = backgroundAllowedTools(params.allowedTools);
            const tag = `kairo-bg-${project.slug}-${randomUUID().slice(0, 8)}`;
            const job = await ledger.createJob({
              project: project.slug,
              title: params.title,
              instructions: params.instructions,
              authorityCeiling,
              scheduledFor: at.toISOString(),
              requestedBudgetUsd: budgetUsd,
              allowedTools: toolCap.tools,
              allowedToolsSource: toolCap.source,
              sourceSession: toolContext.sessionId ?? sessionKey,
            });

            let handle;
            try {
              const deliveryMode: "none" | "announce" =
                params.announce === false ? "none" : "announce";
              const scheduleRequest = {
                sessionKey,
                agentId: toolContext.agentId,
                at,
                deleteAfterRun: true,
                deliveryMode,
                name: `KAIRO: ${params.title}`,
                tag,
                message: backgroundPrompt({
                  project: project.slug,
                  jobId: job.id,
                  title: params.title,
                  instructions: params.instructions,
                  authorityCeiling,
                  requestedBudgetUsd: budgetUsd,
                  allowedTools: toolCap.tools,
                }),
                allowedTools: toolCap.tools,
              };
              handle = await api.session.workflow.scheduleSessionTurn(scheduleRequest);
              if (!handle) throw new Error("OpenClaw did not return a scheduler handle for KAIRO background work.");
              const queued = await ledger.linkScheduler(project.slug, job.id, {
                schedulerId: handle.id,
                schedulerTag: tag,
              });
              return jsonResult({
                job: compact(queued),
                schedule: {
                  id: handle.id,
                  tag,
                  project: project.slug,
                  at: at.toISOString(),
                  authority_ceiling: authorityCeiling,
                  allowed_tools: toolCap.tools,
                  delivery_mode: params.announce === false ? "none" : "announce",
                },
                limitation:
                  "KAIRO enforces this job's exact tool cap through OpenClaw Cron and records KAIRO-owned usage. requestedBudgetUsd remains advisory until Gate 4 proves a pre-call model-spend enforcement seam.",
              });
            } catch (error) {
              const reason = error instanceof Error ? error.message : String(error);
              try {
                await ledger.failJob(project.slug, job.id, { reason: `Scheduling failed: ${reason}` });
              } catch {
                // Preserve the original scheduler error if ledger failure reporting also fails.
              }
              if (handle) {
                try {
                  await api.session.workflow.unscheduleSessionTurnsByTag({ sessionKey, tag });
                } catch {
                  // Best-effort compensation; the durable failed job records that manual reconciliation may be needed.
                }
              }
              throw error;
            }
          },
        };
      },
    }),
  ],
});
