import { KairoJobUsageLedger } from "@kairo/core";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";

function resolveDataDir(pluginConfig: unknown): string | undefined {
  if (!pluginConfig || typeof pluginConfig !== "object" || Array.isArray(pluginConfig)) return undefined;
  const dataDir = (pluginConfig as { dataDir?: unknown }).dataDir;
  return typeof dataDir === "string" && dataDir.trim() ? dataDir.trim() : undefined;
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
}

export function registerKairoUsageHooks(api: OpenClawPluginApi): void {
  const dataDir = resolveDataDir(api.pluginConfig);
  if (!dataDir) return;

  const usage = new KairoJobUsageLedger({ dataDir });
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

  api.on("llm_output", async (event, ctx) => {
    const schedulerId = ctx.jobId?.trim();
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
    const schedulerId = schedulerByRun.get(runId);
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
