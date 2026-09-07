import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";
import plugin from "./index.js";

function createFakeApi(
  dataDir: string,
  options: {
    scheduleSessionTurn?: (params: any) => Promise<any>;
    unscheduleSessionTurnsByTag?: (params: any) => Promise<any>;
  } = {},
) {
  const tools = new Map<string, any>();
  const factories = new Map<string, any>();
  const scheduleSessionTurn =
    options.scheduleSessionTurn ??
    (async (params: any) => ({ id: "cron_test", pluginId: "kairo-tools", sessionKey: params.sessionKey, kind: "session-turn" }));
  const unscheduleSessionTurnsByTag =
    options.unscheduleSessionTurnsByTag ?? (async () => ({ removed: 1, failed: 0 }));

  const api = {
    pluginConfig: { dataDir },
    session: {
      workflow: {
        scheduleSessionTurn,
        unscheduleSessionTurnsByTag,
      },
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
  return { tools, factories, scheduleSessionTurn, unscheduleSessionTurnsByTag };
}

test("plugin exposes the expected stable tool names", () => {
  const metadata = getToolPluginMetadata(plugin);
  assert.ok(metadata);
  assert.equal(metadata.id, "kairo-tools");
  assert.deepEqual(
    metadata.tools.map((tool) => tool.name),
    [
      "kairo_project_create",
      "kairo_project_list",
      "kairo_project_get",
      "kairo_idea_capture",
      "kairo_idea_list",
      "kairo_idea_get",
      "kairo_source_capture",
      "kairo_source_get",
      "kairo_knowledge_capture",
      "kairo_knowledge_get",
      "kairo_job_list",
      "kairo_job_get",
      "kairo_job_start",
      "kairo_job_step_begin",
      "kairo_job_step_complete",
      "kairo_job_complete",
      "kairo_job_fail",
      "kairo_background_schedule",
    ],
  );
});

test("OpenClaw adapter creates a project and durable idea end to end", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-openclaw-tools-"));
  try {
    const { tools } = createFakeApi(root);
    const createProject = tools.get("kairo_project_create");
    const captureIdea = tools.get("kairo_idea_capture");
    const listIdeas = tools.get("kairo_idea_list");
    const getIdea = tools.get("kairo_idea_get");

    const projectResult = await createProject.execute("call-project", {
      name: "ZTIKIX",
      summary: "Visual reaction brand",
    });
    assert.equal(projectResult.details.project.slug, "ztikix");

    const ideaResult = await captureIdea.execute("call-idea", {
      project: "ztikix",
      title: "Rage Bait reaction",
      content: "Explore a ZTIKIX reaction around rage bait.",
      epistemicStatus: "hypothesis",
      originalText: "Maybe we should create a Rage Bait reaction.",
    });
    const ideaId = ideaResult.details.idea.id;
    assert.match(ideaId, /^idea_/);
    assert.equal(ideaResult.details.idea.project_slug, "ztikix");
    assert.equal(ideaResult.details.idea.epistemic_status, "hypothesis");

    const listResult = await listIdeas.execute("call-list", { project: "ztikix" });
    assert.equal(listResult.details.ideas.length, 1);
    assert.equal(listResult.details.ideas[0].id, ideaId);
    assert.equal("body" in listResult.details.ideas[0], false);

    const getResult = await getIdea.execute("call-get", { project: "ztikix", ideaId });
    assert.equal(getResult.details.idea.id, ideaId);
    assert.match(getResult.details.idea.body, /## Original wording/);
    assert.match(getResult.details.idea.body, /Maybe we should create a Rage Bait reaction/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("research memory keeps source evidence separate from epistemic claims", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-research-memory-"));
  try {
    const { tools } = createFakeApi(root);
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const sourceResult = await tools.get("kairo_source_capture").execute("source", {
      project: "ztikix",
      title: "Example evidence",
      kind: "url",
      locator: "https://example.com/evidence",
      summary: "A source used only for adapter testing.",
    });
    const sourceId = sourceResult.details.source.id;
    assert.match(sourceId, /^source_/);

    const claimResult = await tools.get("kairo_knowledge_capture").execute("claim", {
      project: "ztikix",
      title: "Tentative finding",
      claim: "This finding still needs independent verification.",
      epistemicStatus: "hypothesis",
      confidence: 0.4,
      sourceIds: [sourceId],
    });
    assert.equal(claimResult.details.claim.epistemic_status, "hypothesis");
    assert.deepEqual(claimResult.details.claim.source_ids, [sourceId]);

    const getClaim = await tools.get("kairo_knowledge_get").execute("get-claim", {
      project: "ztikix",
      claimId: claimResult.details.claim.id,
    });
    assert.match(getClaim.details.claim.body, /still needs independent verification/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("background scheduling creates and links a durable KAIRO job before returning", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-background-job-"));
  const scheduled: any[] = [];
  try {
    const { tools, factories } = createFakeApi(root, {
      async scheduleSessionTurn(params) {
        scheduled.push(params);
        return { id: "cron_123", pluginId: "kairo-tools", sessionKey: params.sessionKey, kind: "session-turn" };
      },
    });
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const concrete = factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      sessionId: "session-uuid-test",
      agentId: "main",
      sandboxed: false,
    });
    assert.ok(concrete);

    const result = await concrete.execute("schedule-call", {
      project: "ztikix",
      title: "Overnight trend scan",
      instructions: "Review relevant public trend signals and report only supported findings.",
      at: "2030-01-02T03:00:00+02:00",
      authorityCeiling: "A2",
      requestedBudget: 0.5,
    });

    assert.equal(scheduled.length, 1);
    assert.equal(scheduled[0].sessionKey, "agent:main:session:test");
    assert.equal(scheduled[0].agentId, "main");
    assert.equal(scheduled[0].deleteAfterRun, true);
    assert.equal(scheduled[0].deliveryMode, "announce");
    assert.match(scheduled[0].tag, /^kairo-bg-ztikix-/);
    assert.match(scheduled[0].message, /Authority ceiling: A2/);
    assert.match(scheduled[0].message, /Requested model budget: 0.5/);
    assert.match(scheduled[0].message, /kairo_job_start/);
    assert.match(scheduled[0].message, /kairo_job_step_begin/);
    assert.match(scheduled[0].message, /kairo_job_step_complete/);
    assert.match(scheduled[0].message, /already_started/);
    assert.match(scheduled[0].message, /do not repeat the mutation blindly/i);
    assert.match(scheduled[0].message, /kairo_job_complete/);
    assert.match(scheduled[0].message, /Do not publish, send messages, purchase, trade, delete external data/);

    const job = result.details.job;
    assert.match(job.id, /^job_/);
    assert.equal(job.status, "queued");
    assert.equal(job.scheduler_id, "cron_123");
    assert.equal(job.requested_budget, 0.5);
    assert.equal(job.budget_enforced, false);
    assert.match(scheduled[0].message, new RegExp(job.id));

    const listed = await tools.get("kairo_job_list").execute("list-jobs", { project: "ztikix" });
    assert.equal(listed.details.jobs.length, 1);
    assert.equal(listed.details.jobs[0].id, job.id);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("scheduled job tools persist replay checkpoints and completed state", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-job-tools-"));
  try {
    const { tools, factories } = createFakeApi(root);
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });
    const concrete = factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });
    const scheduled = await concrete.execute("schedule-call", {
      project: "ztikix",
      title: "Lifecycle",
      instructions: "Test lifecycle.",
      at: "2030-01-02T03:00:00+02:00",
    });
    const jobId = scheduled.details.job.id;

    const running = await tools.get("kairo_job_start").execute("start", { project: "ztikix", jobId });
    assert.equal(running.details.job.status, "running");

    const begin = await tools.get("kairo_job_step_begin").execute("step-begin", {
      project: "ztikix",
      jobId,
      stepKey: "write:report",
      description: "Persist the final internal report.",
    });
    assert.equal(begin.details.disposition, "started");
    assert.equal(begin.details.step.status, "started");

    const duplicateBegin = await tools.get("kairo_job_step_begin").execute("step-begin-retry", {
      project: "ztikix",
      jobId,
      stepKey: "write:report",
    });
    assert.equal(duplicateBegin.details.disposition, "already_started");

    await assert.rejects(
      tools.get("kairo_job_complete").execute("too-early", {
        project: "ztikix",
        jobId,
        summary: "Must not complete while the mutation outcome is unresolved.",
      }),
      /unresolved execution steps/i,
    );

    const stepComplete = await tools.get("kairo_job_step_complete").execute("step-complete", {
      project: "ztikix",
      jobId,
      stepKey: "write:report",
      summary: "Internal report persisted.",
    });
    assert.equal(stepComplete.details.disposition, "completed");
    assert.equal(stepComplete.details.step.status, "completed");

    const duplicateComplete = await tools.get("kairo_job_step_complete").execute("step-complete-retry", {
      project: "ztikix",
      jobId,
      stepKey: "write:report",
      summary: "Retry should preserve the first completion.",
    });
    assert.equal(duplicateComplete.details.disposition, "already_completed");
    assert.equal(duplicateComplete.details.step.summary, "Internal report persisted.");

    const complete = await tools.get("kairo_job_complete").execute("complete", {
      project: "ztikix",
      jobId,
      summary: "Lifecycle completed.",
    });
    assert.equal(complete.details.job.status, "completed");

    const getJob = await tools.get("kairo_job_get").execute("get", { project: "ztikix", jobId });
    assert.match(getJob.details.job.body, /## Execution checkpoints/);
    assert.match(getJob.details.job.body, /write:report/);
    assert.match(getJob.details.job.body, /Lifecycle completed/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("scheduler failure is written to the KAIRO job ledger", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-scheduler-failure-"));
  try {
    const { tools, factories } = createFakeApi(root, {
      async scheduleSessionTurn() {
        throw new Error("Cron unavailable");
      },
    });
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });
    const concrete = factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });

    await assert.rejects(
      () =>
        concrete.execute("schedule-call", {
          project: "ztikix",
          title: "Will fail",
          instructions: "Test failure persistence.",
          at: "2030-01-02T03:00:00+02:00",
        }),
      /Cron unavailable/,
    );

    const jobs = await tools.get("kairo_job_list").execute("list", { project: "ztikix" });
    assert.equal(jobs.details.jobs.length, 1);
    assert.equal(jobs.details.jobs[0].status, "failed");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("background scheduler requires a runtime session", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-background-nosession-"));
  try {
    const { factories } = createFakeApi(root);
    const factory = factories.get("kairo_background_schedule");
    assert.ok(factory);
    assert.equal(factory({ agentId: "main", sandboxed: false }), null);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("background scheduler rejects timezone-ambiguous timestamps", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-background-time-"));
  try {
    const { tools, factories } = createFakeApi(root);
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });
    const concrete = factories.get("kairo_background_schedule")({
      sessionKey: "agent:main:session:test",
      agentId: "main",
    });
    await assert.rejects(
      () =>
        concrete.execute("schedule-call", {
          project: "ztikix",
          title: "Ambiguous schedule",
          instructions: "Do something later.",
          at: "2030-01-02T03:00:00",
        }),
      /must include Z or an explicit UTC offset/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("plugin refuses a relative runtime data directory", async () => {
  const { tools } = createFakeApi("./relative-data");
  await assert.rejects(
    () => tools.get("kairo_project_list").execute("call-list", {}),
    /dataDir must be an absolute path/,
  );
});