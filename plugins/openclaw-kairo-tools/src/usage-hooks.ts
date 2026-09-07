import { KairoJobLedger, KairoJobUsageLedger } from "@kairo/core";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";

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
    schedulerByRun.set(runId, schedulerId);
    return schedulerId;
  }

  api.on("llm_output", async (event, ctx) => {
    const schedulerId = ctx.jobId?.trim() || schedulerByRun.get(event.runId);
    if (!schedulerId) return;
    schedulerByRun.set(event.runId, schedulerId);

    await serialized(schedulerId, () =>
      usage.recordLlmOutputBySchedulerId(schedulerId, {
        runId: event.runId,
        sessionId: event.sessionId,
        provider: event.provider,
        model: event.model,
        resolvedRef: event.resolvedRef,
        harnessId: event.harnessId,
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
        usage: snapshot.usage,
        turnUsd: finiteNumber(snapshot.turnUsd),
        durationMs: finiteNumber(snapshot.durationMs),
        fallbackUsed: snapshot.fallbackUsed,
      }),
    );
  });
}
