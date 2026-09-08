import type {
  OpenClawPluginService,
  OpenClawPluginServiceContext,
} from "openclaw/plugin-sdk/plugin-entry";

type GatewayCron = NonNullable<
  ReturnType<NonNullable<OpenClawPluginServiceContext["getCron"]>>
>;

export type GatewayCronAgentTurnRequest = {
  sessionKey: string;
  agentId?: string;
  at: Date;
  name: string;
  tag: string;
  message: string;
  announce: boolean;
  toolsAllow: string[];
};

export type GatewayCronAgentTurnHandle = {
  id: string;
};

type AgentTurnCronCreateInput = {
  name: string;
  description: string;
  enabled: true;
  schedule: {
    kind: "at";
    at: string;
  };
  sessionTarget: string;
  agentId?: string;
  deleteAfterRun: true;
  wakeMode: "now";
  payload: {
    kind: "agentTurn";
    message: string;
    toolsAllow: string[];
  };
  delivery:
    | {
        mode: "announce";
        channel: "last";
      }
    | {
        mode: "none";
      };
};

function readCronJobId(value: unknown): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const id = (value as { id?: unknown }).id;
  return typeof id === "string" && id.trim() ? id.trim() : undefined;
}

function cronCreateInput(input: AgentTurnCronCreateInput): Parameters<GatewayCron["add"]>[0] {
  // OpenClaw 2026.9.2 exposes a conservative public service-cron input type,
  // while the same pinned runtime normalizer accepts the full CronJobCreate
  // shapes used by its own isolated agent scheduler, including payload.toolsAllow.
  // Keep this compatibility cast in one place so a future OpenClaw upgrade has
  // one boundary to revalidate.
  return input as unknown as Parameters<GatewayCron["add"]>[0];
}

export function createGatewayCronBridge(): {
  service: OpenClawPluginService;
  scheduleAgentTurn: (request: GatewayCronAgentTurnRequest) => Promise<GatewayCronAgentTurnHandle>;
  remove: (id: string) => Promise<void>;
} {
  let getCron: OpenClawPluginServiceContext["getCron"] | undefined;

  const requireCron = (): GatewayCron => {
    if (!getCron) {
      throw new Error(
        "KAIRO background scheduling requires the KAIRO Gateway cron service to be active.",
      );
    }
    const cron = getCron();
    if (!cron) {
      throw new Error("OpenClaw Gateway cron service is unavailable to KAIRO.");
    }
    return cron;
  };

  const service: OpenClawPluginService = {
    id: "kairo-tools-cron",
    start(ctx) {
      getCron = ctx.getCron;
      if (!getCron) {
        ctx.logger.warn(
          "kairo-tools: Gateway cron service is unavailable; background scheduling will fail closed.",
        );
      }
    },
    stop() {
      getCron = undefined;
    },
  };

  return {
    service,
    async scheduleAgentTurn(request) {
      const cron = requireCron();
      const result = await cron.add(
        cronCreateInput({
          name: `plugin:kairo-tools:tag:${request.tag}:${request.sessionKey}:${request.name}`,
          description: request.name,
          enabled: true,
          schedule: {
            kind: "at",
            at: request.at.toISOString(),
          },
          sessionTarget: `session:${request.sessionKey}`,
          ...(request.agentId ? { agentId: request.agentId } : {}),
          deleteAfterRun: true,
          wakeMode: "now",
          payload: {
            kind: "agentTurn",
            message: request.message,
            toolsAllow: [...request.toolsAllow],
          },
          delivery: request.announce
            ? {
                mode: "announce",
                channel: "last",
              }
            : {
                mode: "none",
              },
        }),
      );
      const id = readCronJobId(result);
      if (!id) {
        throw new Error("OpenClaw Cron did not return a scheduler id for KAIRO background work.");
      }
      return { id };
    },
    async remove(id) {
      const cron = requireCron();
      const result = await cron.remove(id);
      if (result?.removed === false) {
        throw new Error(`OpenClaw Cron did not remove scheduler job ${id}.`);
      }
    },
  };
}
