import {
  definePluginEntry,
  type OpenClawPluginApi,
} from "openclaw/plugin-sdk/plugin-entry";
import {
  getToolPluginMetadata,
  toolPluginMetadataSymbol,
} from "openclaw/plugin-sdk/tool-plugin";
import { createGatewayCronBridge } from "./gateway-cron.js";
import toolPlugin from "./index.js";

const metadata = getToolPluginMetadata(toolPlugin);
if (!metadata) {
  throw new Error("KAIRO tool metadata is unavailable.");
}

const gatewayCron = createGatewayCronBridge();

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
