import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import plugin from "./entry.js";

type FakeRuntimeOptions = {
  cronList?: () => Promise<any[]>;
  cronAdd?: (input: any) => Promise<any>;
  cronRemove?: (id: string) => Promise<any>;
};

function createFakeRuntime(dataDir: string, options: FakeRuntimeOptions = {}) {
  const tools = new Map<string, any>();
  const factories = new Map<string, any>();
  const services = new Map<string, any>();
  const hooks = new Map<string, any[]>();
  const cronAdds: any[] = [];
  const cronRemoves: string[] = [];

  const cron = {
    async list() {
      if (options.cronList) return await options.cronList();
      return [];
    },
    async add(input: any) {
      cronAdds.push(input);
      if (options.cronAdd) return await options.cronAdd(input);
      return { id: "cron_gateway_123" };
    },
    async update() {
      return {};
    },
    async remove(id: string) {
      cronRemoves.push(id);
      if (options.cronRemove) return await options.cronRemove(id);
      return { removed: true };
    },
    async removeStaleJobFamily() {
      return 0;
    },
  };

  const api = {
    pluginConfig: { dataDir },
    session: {
      workflow: {
        async scheduleSessionTurn() {
          throw new Error("bundled-only scheduleSessionTurn must not be used by installed KAIRO");
        },
        async unscheduleSessionTurnsByTag() {
          throw new Error("bundled-only unscheduleSessionTurnsByTag must not be used by installed KAIRO");
        },
      },
    },
    registerService(service: any) {
      services.set(service.id, service);
    },
    on(hookName: string, handler: any) {
      const handlers = hooks.get(hookName) ?? [];
      handlers.push(handler);
      hooks.set(hookName, handlers);
    },
    registerTool(tool: any, opts?: { name?: string }) {
      if (typeof tool === "function") {
        if (!opts?.name) throw new Error("Factory tool registration is missing a stable name.");
        factories.set(opts.name, tool);
        return;
      }
      tools.set(tool.name, tool);
    },
  };

  (plugin as any).register(api);

  const serviceContext = {
    config: {
      plugins: {
        entries: {
          "kairo-tools": {
            config: { dataDir },
          },
        },
      },
    },
    stateDir: dataDir,
    logger: {
      debug() {},
      info() {},
      warn() {},
      error() {},
    },
    getCron: () => cron,
  };

  return {
    tools,
    factories,
    services,
    cronAdds,
    cronRemoves,
    async triggerHook(hookName: string, event: any = {}) {
      for (const handler of hooks.get(hookName) ?? []) {
        await handler(event, {
          config: serviceContext.config,
          workspaceDir: dataDir,
          getCron: () => cron,
          abortSignal: new AbortController().signal,
        });
      }
    },
    async startGatewayServices() {
      for (const service of services.values()) {
        await service.start(serviceContext);
      }
    },
    async stopGatewayServices() {
      for (const service of services.values()) {
        await service.stop?.(serviceContext);
      }
    },
  };
}

test("advanced entry schedules KAIRO work through the Gateway cron service", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-gateway-cron-"));
  const runtime = createFakeRuntime(root);
  try {
    assert.ok(runtime.services.has("kairo-tools-cron"));
    await runtime.startGatewayServices();
    await runtime.tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const concrete = runtime.factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      sessionId: "session-uuid-test",
      agentId: "main",
      sandboxed: false,
    });
    assert.ok(concrete);

    const result = await concrete.execute("schedule-call", {
      project: "ztikix",
      title: "Gateway cron proof",
      instructions: "Read the project and produce a concise internal summary.",
      at: "2030-01-02T03:00:00+02:00",
      authorityCeiling: "A2",
      requestedBudget: 0.5,
    });

    assert.equal(runtime.cronAdds.length, 1);
    const scheduled = runtime.cronAdds[0];
    assert.equal(scheduled.sessionTarget, "session:agent:main:session:test");
    assert.equal(scheduled.agentId, "main");
    assert.equal(scheduled.schedule.kind, "at");
    assert.equal(scheduled.schedule.at, "2030-01-02T01:00:00.000Z");
    assert.equal(scheduled.deleteAfterRun, true);
    assert.equal(scheduled.wakeMode, "now");
    assert.equal(scheduled.delivery.mode, "announce");
    assert.equal(scheduled.delivery.channel, "last");
    assert.equal(scheduled.payload.kind, "agentTurn");
    assert.match(scheduled.payload.message, /KAIRO BACKGROUND WORK/);
    assert.match(scheduled.payload.message, /kairo_job_start/);
    assert.match(scheduled.payload.message, /kairo_job_complete/);
    assert.match(scheduled.name, /^plugin:kairo-tools:tag:kairo-bg-ztikix-/);

    const job = result.details.job;
    assert.equal(job.status, "queued");
    assert.equal(job.scheduler_id, "cron_gateway_123");
    assert.match(job.scheduler_tag, /^kairo-bg-ztikix-/);
    assert.equal(result.details.schedule.id, "cron_gateway_123");
  } finally {
    await runtime.stopGatewayServices();
    await rm(root, { recursive: true, force: true });
  }
});

test("background scheduling fails closed when the Gateway cron service is not active", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-gateway-cron-inactive-"));
  const runtime = createFakeRuntime(root);
  try {
    await runtime.tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });
    const concrete = runtime.factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });

    await assert.rejects(
      () =>
        concrete.execute("schedule-call", {
          project: "ztikix",
          title: "No gateway service",
          instructions: "This must fail durably rather than pretend to schedule.",
          at: "2030-01-02T03:00:00+02:00",
        }),
      /Gateway cron service to be active/,
    );

    const jobs = await runtime.tools.get("kairo_job_list").execute("list", { project: "ztikix" });
    assert.equal(jobs.details.jobs.length, 1);
    assert.equal(jobs.details.jobs[0].status, "failed");
  } finally {
    await runtime.stopGatewayServices();
    await rm(root, { recursive: true, force: true });
  }
});

test("missing Cron id is recorded as a durable scheduler failure", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-gateway-cron-no-id-"));
  const runtime = createFakeRuntime(root, {
    async cronAdd() {
      return {};
    },
  });
  try {
    await runtime.startGatewayServices();
    await runtime.tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });
    const concrete = runtime.factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });

    await assert.rejects(
      () =>
        concrete.execute("schedule-call", {
          project: "ztikix",
          title: "Missing scheduler id",
          instructions: "Exercise scheduler failure persistence.",
          at: "2030-01-02T03:00:00+02:00",
        }),
      /did not return a scheduler id/,
    );

    const jobs = await runtime.tools.get("kairo_job_list").execute("list", { project: "ztikix" });
    assert.equal(jobs.details.jobs.length, 1);
    assert.equal(jobs.details.jobs[0].status, "failed");
  } finally {
    await runtime.stopGatewayServices();
    await rm(root, { recursive: true, force: true });
  }
});
test("cron reconciliation preserves queued job when scheduler exists", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-reconcile-present-"));
  const runtime = createFakeRuntime(root, {
    async cronList() {
      return [{ id: "cron_gateway_123" }];
    },
  });

  try {
    await runtime.startGatewayServices();
    await runtime.tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const concrete = runtime.factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });

    const scheduled = await concrete.execute("schedule-call", {
      project: "ztikix",
      title: "Scheduler present",
      instructions: "Remain queued.",
      at: "2030-01-02T03:00:00Z",
    });

    const jobId = scheduled.details.job.id;

    await runtime.triggerHook("cron_reconciled", {
      reason: "startup",
      enabled: true,
    });

    const result = await runtime.tools.get("kairo_job_get").execute("get", {
      project: "ztikix",
      jobId,
    });

    assert.equal(result.details.job.status, "queued");
  } finally {
    await runtime.stopGatewayServices();
    await rm(root, { recursive: true, force: true });
  }
});
test("cron reconciliation fails queued job when scheduler is missing", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-reconcile-missing-"));
  const runtime = createFakeRuntime(root, {
    async cronList() {
      return [];
    },
  });

  try {
    await runtime.startGatewayServices();
    await runtime.tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const concrete = runtime.factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });

    const scheduled = await concrete.execute("schedule-call", {
      project: "ztikix",
      title: "Scheduler missing",
      instructions: "Fail explicitly if scheduler disappears.",
      at: "2030-01-02T03:00:00Z",
    });

    const jobId = scheduled.details.job.id;

    await runtime.triggerHook("cron_reconciled", {
      reason: "startup",
      enabled: true,
    });

    const result = await runtime.tools.get("kairo_job_get").execute("get", {
      project: "ztikix",
      jobId,
    });

    assert.equal(result.details.job.status, "failed");
    assert.match(result.details.job.failure_reason, /scheduler.*missing/i);
  } finally {
    await runtime.stopGatewayServices();
    await rm(root, { recursive: true, force: true });
  }
});
