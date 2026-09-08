import { KairoJobLedger, KairoJobUsageLedger } from "@kairo/core";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";

const MAX_RUN_BINDINGS = 1024;

function resolveDataDir(pluginConfig: unknown): string | undefined {
  if (!pluginConfig || typeof pluginConfig !== "object" || Array.isArray(pluginConfig)) return undefined;
  const dataDir = (pluginConfig as { dataDir?: unknown }).dataDir;
  return typeof dataDir === "string" && dataDir.trim() ? dataDir.trim() : undefined;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
}

function readStringField(value: unknown, key: string): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "string" && field.trim() ? field.trim() : undefined;
}

export function registerKairoUsageHooks(api: OpenClawPluginApi): void {
  const dataDir = resolveDataDir(api.pluginConfig);
  if (!dataDir) return;

  const usage = new KairoJobUsageLedger({ dataDir });
  const jobs = new KairoJobLedger({ dataDir });
  const schedulerByRun = new Map<string, string>();
  const queues = new Map<string, Promise<void>>();

  function rememberRun(runId: string, schedulerId: string): void {
    schedulerByRun.delete(runId);
    schedulerByRun.set(runId, schedulerId);
    while (schedulerByRun.size > MAX_RUN_BINDINGS) {
      const oldest = schedulerByRun.keys().next().value as string | undefined;
      if (!oldest) break;
      schedulerByRun.delete(oldest);
    }
  }

  async function serialized(schedulerId: string, operation: () => Promise<unknown>): Promise<void> {
    const previous = queues.get(schedulerId) ?? Promise.resolve();
    const current = previous.catch(() => undefined).then(operation).then(() => undefined);
    queues.set(schedulerId, current);
    try {
      await current;
    } finally {
      if (queues.get(schedulerId) === current) queues.delete(schedulerId);
    }
  }

  async function bindKnownScheduler(params: {
    runId: string;
    schedulerId: string;
    sessionId?: string;
    trigger?: string;
  }): Promise<boolean> {
    const match = await usage.findJobBySchedulerId(params.schedulerId);
    if (!match) return false;
    rememberRun(params.runId, params.schedulerId);
    await serialized(params.schedulerId, () =>
      usage.recordRunBinding(match.project_slug, match.job_id, {
        schedulerId: params.schedulerId,
        runId: params.runId,
        sessionId: params.sessionId,
        trigger: params.trigger,
      }),
    );
    return true;
  }

  async function bindRunFromKairoJobStart(event: {
    runId?: string;
    toolName?: string;
    params?: unknown;
    error?: unknown;
  }): Promise<string | undefined> {
    if (event.toolName !== "kairo_job_start" || event.error) return undefined;
    const runId = event.runId?.trim();
    const project = readStringField(event.params, "project");
    const jobId = readStringField(event.params, "jobId");
    if (!runId || !project || !jobId) return undefined;

    const job = await jobs.getJob(project, jobId);
    const schedulerId = typeof job.scheduler_id === "string" ? job.scheduler_id.trim() : "";
    if (!schedulerId) return undefined;
    rememberRun(runId, schedulerId);
    await serialized(schedulerId, () =>
      usage.recordRunBinding(project, jobId, {
        schedulerId,
        runId,
        trigger: "cron",
      }),
    );
    return schedulerId;
  }

  api.on(
    "before_agent_reply",
    async (_event, ctx) => {
      const runId = ctx.runId?.trim();
      const schedulerId = ctx.jobId?.trim();
      if (!runId || !schedulerId) return;
      await bindKnownScheduler({
        runId,
        schedulerId,
        sessionId: ctx.sessionId,
        trigger: ctx.trigger,
      });
    },
    { eligibleTriggers: ["cron"] as const },
  );

  api.on("model_call_started", async (event) => {
    const schedulerId = schedulerByRun.get(event.runId);
    if (!schedulerId) return;
    await serialized(schedulerId, () =>
      usage.recordModelCallStartedBySchedulerId(schedulerId, {
        runId: event.runId,
        callId: event.callId,
        sessionId: event.sessionId,
        provider: event.provider,
        model: event.model,
        api: event.api,
        transport: event.transport,
        contextTokenBudget: finiteNumber(event.contextTokenBudget),
      }),
    );
  });

  api.on("model_call_ended", async (event) => {
    const schedulerId = schedulerByRun.get(event.runId);
    if (!schedulerId) return;
    await serialized(schedulerId, () =>
      usage.recordModelCallEndedBySchedulerId(schedulerId, {
        runId: event.runId,
        callId: event.callId,
        sessionId: event.sessionId,
        provider: event.provider,
        model: event.model,
        api: event.api,
        transport: event.transport,
        durationMs: finiteNumber(event.durationMs),
        outcome: event.outcome,
        errorCategory: event.errorCategory,
        failureKind: event.failureKind,
        requestPayloadBytes: finiteNumber(event.requestPayloadBytes),
        responseStreamBytes: finiteNumber(event.responseStreamBytes),
        timeToFirstByteMs: finiteNumber(event.timeToFirstByteMs),
        upstreamRequestIdHash: event.upstreamRequestIdHash,
      }),
    );
  });

  api.on("llm_output", async (event, ctx) => {
    const directSchedulerId = ctx.jobId?.trim();
    if (directSchedulerId && !schedulerByRun.has(event.runId)) {
      await bindKnownScheduler({
        runId: event.runId,
        schedulerId: directSchedulerId,
        sessionId: event.sessionId,
        trigger: ctx.trigger,
      });
    }
    const schedulerId = schedulerByRun.get(event.runId);
    if (!schedulerId) return;

    await serialized(schedulerId, () =>
      usage.recordUsageObservationBySchedulerId(schedulerId, {
        runId: event.runId,
        sessionId: event.sessionId,
        provider: event.provider,
        model: event.model,
        resolvedRef: event.resolvedRef,
        harnessId: event.harnessId,
        contextTokenBudget: finiteNumber(event.contextTokenBudget),
        usage: event.usage,
      }),
    );
  });

  api.on("after_tool_call", async (event, ctx) => {
    const runId = event.runId ?? ctx.runId;
    if (!runId) return;
    let schedulerId = schedulerByRun.get(runId);
    if (!schedulerId) schedulerId = await bindRunFromKairoJobStart(event);
    if (!schedulerId) return;

    await serialized(schedulerId, () =>
      usage.recordToolCallBySchedulerId(schedulerId, {
        runId,
        toolCallId: event.toolCallId ?? ctx.toolCallId,
        toolName: event.toolName,
        error: event.error,
        durationMs: finiteNumber(event.durationMs),
      }),
    );
  });

  api.on("reply_payload_sending", async (event) => {
    const runId = event.runId;
    const snapshot = event.usageState;
    if (!runId || !snapshot) return;
    const schedulerId = schedulerByRun.get(runId);
    if (!schedulerId) return;

    await serialized(schedulerId, () =>
      usage.recordFinalSnapshotBySchedulerId(schedulerId, {
        runId,
        sessionId: snapshot.sessionId,
        provider: snapshot.provider,
        model: snapshot.model,
        resolvedRef: snapshot.resolvedRef,
        requested: snapshot.requested,
        usage: snapshot.usage,
        turnUsd: finiteNumber(snapshot.turnUsd),
        durationMs: finiteNumber(snapshot.durationMs),
        fallbackUsed: snapshot.fallbackUsed,
      }),
    );
  });
}
