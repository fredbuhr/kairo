import {
  definePluginEntry,
  type OpenClawPluginApi,
} from "openclaw/plugin-sdk/plugin-entry";
import {
  getToolPluginMetadata,
  toolPluginMetadataSymbol,
} from "openclaw/plugin-sdk/tool-plugin";
import { createGatewayCronBridge } from "./gateway-cron.js";
import toolPlugin, { ledgerFor, storeFor } from "./index.js";
import { registerKairoUsageHooks } from "./usage-hooks.js";

const metadata = getToolPluginMetadata(toolPlugin);
if (!metadata) {
  throw new Error("KAIRO tool metadata is unavailable.");
}

const pluginId = metadata.id;
const gatewayCron = createGatewayCronBridge();

function resolvePluginDataDir(config: unknown): string | undefined {
  if (!config || typeof config !== "object" || Array.isArray(config)) return undefined;
  const plugins = (config as { plugins?: unknown }).plugins;
  if (!plugins || typeof plugins !== "object" || Array.isArray(plugins)) return undefined;
  const entries = (plugins as { entries?: unknown }).entries;
  if (!entries || typeof entries !== "object" || Array.isArray(entries)) return undefined;
  const entry = (entries as Record<string, unknown>)[pluginId];
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) return undefined;
  const pluginConfig = (entry as { config?: unknown }).config;
  if (!pluginConfig || typeof pluginConfig !== "object" || Array.isArray(pluginConfig)) return undefined;
  const dataDir = (pluginConfig as { dataDir?: unknown }).dataDir;
  return typeof dataDir === "string" && dataDir.trim() ? dataDir.trim() : undefined;
}

function resolveScheduledAt(params: Record<string, unknown>): Date {
  const rawAt = params.at;
  if (rawAt instanceof Date) return rawAt;
  if (typeof rawAt === "string" || typeof rawAt === "number") {
    const at = new Date(rawAt);
    if (Number.isFinite(at.getTime())) return at;
  }
  const delayMs = params.delayMs;
  if (typeof delayMs === "number" && Number.isFinite(delayMs) && delayMs >= 0) {
    return new Date(Date.now() + Math.max(1, Math.floor(delayMs)));
  }
  throw new Error("KAIRO background scheduling requires a valid one-shot time.");
}

const plugin = definePluginEntry({
  id: metadata.id,
  name: metadata.name,
  description: metadata.description,
  configSchema: toolPlugin.configSchema,
  register(api) {
    api.registerService(gatewayCron.service);
    registerKairoUsageHooks(api);

    api.on("cron_reconciled", async (event, ctx) => {
      if (!event.enabled || ctx.abortSignal.aborted) return;

      const dataDir = resolvePluginDataDir(ctx.config);
      const cron = ctx.getCron?.();
      if (!dataDir || !cron) return;

      const reconciliationStartedAt = Date.now();
      const cronJobs = await cron.list({ includeDisabled: true });
      ctx.abortSignal.throwIfAborted();

      const schedulerIds = new Set(cronJobs.map((job) => job.id));
      const store = storeFor(dataDir);
      const ledger = ledgerFor(dataDir);
      const projects = await store.listProjects();

      for (const project of projects) {
        ctx.abortSignal.throwIfAborted();
        const jobs = await ledger.listJobs(project.slug);

        for (const job of jobs) {
          if (job.status !== "queued") continue;
          if (job.scheduler_kind !== "openclaw-session-turn") continue;
          if (!job.scheduler_id || schedulerIds.has(job.scheduler_id)) continue;

          const queuedAt = Date.parse(String(job.queued_at ?? ""));
          const scheduledFor = Date.parse(String(job.scheduled_for ?? ""));
          if (!Number.isFinite(queuedAt) || queuedAt > reconciliationStartedAt) continue;
          if (!Number.isFinite(scheduledFor) || scheduledFor <= reconciliationStartedAt) continue;

          ctx.abortSignal.throwIfAborted();
          await ledger.failJob(project.slug, job.id, {
            reason: `Reconciliation detected scheduler missing from OpenClaw Cron: ${job.scheduler_id}.`,
          });
        }
      }
    });

    const schedulerIdsByTag = new Map<string, Set<string>>();
    const scheduleSessionTurn: typeof api.session.workflow.scheduleSessionTurn = async (rawParams) => {
      const params = rawParams as unknown as Record<string, unknown>;
      const sessionKey = typeof params.sessionKey === "string" ? params.sessionKey.trim() : "";
      const message = typeof params.message === "string" ? params.message.trim() : "";
      if (!sessionKey || !message) {
        throw new Error("KAIRO background scheduling requires a session key and message.");
      }
      const tag = typeof params.tag === "string" && params.tag.trim()
        ? params.tag.trim()
        : `kairo-bg-${Date.now()}`;
      const name = typeof params.name === "string" && params.name.trim()
        ? params.name.trim()
        : "KAIRO background work";
      const agentId = typeof params.agentId === "string" && params.agentId.trim()
        ? params.agentId.trim()
        : undefined;
      const handle = await gatewayCron.scheduleAgentTurn({
        sessionKey,
        agentId,
        at: resolveScheduledAt(params),
        name,
        tag,
        message,
        announce: params.deliveryMode !== "none",
      });
      const key = `${sessionKey}\u0000${tag}`;
      const ids = schedulerIdsByTag.get(key) ?? new Set<string>();
      ids.add(handle.id);
      schedulerIdsByTag.set(key, ids);
      return {
        id: handle.id,
        pluginId: metadata.id,
        sessionKey,
        kind: "session-turn" as const,
      };
    };

    const unscheduleSessionTurnsByTag: typeof api.session.workflow.unscheduleSessionTurnsByTag = async (
      rawParams,
    ) => {
      const params = rawParams as unknown as Record<string, unknown>;
      const sessionKey = typeof params.sessionKey === "string" ? params.sessionKey.trim() : "";
      const tag = typeof params.tag === "string" ? params.tag.trim() : "";
      if (!sessionKey || !tag) return { removed: 0, failed: 0 };
      const key = `${sessionKey}\u0000${tag}`;
      const ids = [...(schedulerIdsByTag.get(key) ?? [])];
      let removed = 0;
      let failed = 0;
      for (const id of ids) {
        try {
          await gatewayCron.remove(id);
          removed += 1;
        } catch {
          failed += 1;
        }
      }
      if (failed === 0) schedulerIdsByTag.delete(key);
      return { removed, failed };
    };

    const toolApi = {
      ...api,
      session: {
        ...api.session,
        workflow: {
          ...api.session.workflow,
          scheduleSessionTurn,
          unscheduleSessionTurnsByTag,
        },
      },
    } as OpenClawPluginApi;

    toolPlugin.register(toolApi);
  },
});

// Preserve defineToolPlugin metadata so `openclaw plugins build` continues to
// derive the stable tool contract and config schema from the tool declarations.
Object.defineProperty(plugin, toolPluginMetadataSymbol, {
  value: metadata,
  enumerable: false,
});

export default plugin;
