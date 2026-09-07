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
  } = {},
) {
  const tools = new Map<string, any>();
  const factories = new Map<string, any>();
  const scheduleSessionTurn =
    options.scheduleSessionTurn ??
    (async (params: any) => ({ id: "cron_test", pluginId: "kairo-tools", sessionKey: params.sessionKey, kind: "session-turn" }));

  const api = {
    pluginConfig: { dataDir },
    session: {
      workflow: {
        scheduleSessionTurn,
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
  return { tools, factories, scheduleSessionTurn };
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

test("background scheduler creates a bounded OpenClaw future session turn", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-background-"));
  const scheduled: any[] = [];
  try {
    const { tools, factories } = createFakeApi(root, {
      async scheduleSessionTurn(params) {
        scheduled.push(params);
        return { id: "cron_123", pluginId: "kairo-tools", sessionKey: params.sessionKey, kind: "session-turn" };
      },
    });
    await tools.get("kairo_project_create").execute("project", { name: "ZTIKIX" });

    const factory = factories.get("kairo_background_schedule");
    assert.ok(factory);
    const concrete = factory({
      sessionKey: "agent:main:session:test",
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
    });

    assert.equal(scheduled.length, 1);
    assert.equal(scheduled[0].sessionKey, "agent:main:session:test");
    assert.equal(scheduled[0].agentId, "main");
    assert.equal(scheduled[0].deleteAfterRun, true);
    assert.equal(scheduled[0].deliveryMode, "announce");
    assert.match(scheduled[0].tag, /^kairo-bg-ztikix-/);
    assert.match(scheduled[0].message, /Authority ceiling: A2/);
    assert.match(scheduled[0].message, /Do not publish, send messages, purchase, trade, delete external data/);
    assert.match(scheduled[0].message, /kairo_source_capture/);
    assert.equal(result.details.schedule.id, "cron_123");
    assert.equal(result.details.schedule.project, "ztikix");
    assert.match(result.details.limitation, /hard model-cost ceilings are not implemented yet/);
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
