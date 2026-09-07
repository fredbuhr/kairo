import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";
import plugin from "./index.js";

function createFakeApi(dataDir: string) {
  const tools = new Map<string, any>();
  const api = {
    pluginConfig: { dataDir },
    registerTool(tool: any) {
      if (typeof tool === "function") throw new Error("Unexpected factory tool in KAIRO V0 tests.");
      tools.set(tool.name, tool);
    },
  };
  (plugin as any).register(api);
  return tools;
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
    ],
  );
});

test("OpenClaw adapter creates a project and durable idea end to end", async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), "kairo-openclaw-tools-"));
  try {
    const tools = createFakeApi(root);
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

test("plugin refuses a relative runtime data directory", async () => {
  const tools = createFakeApi("./relative-data");
  await assert.rejects(
    () => tools.get("kairo_project_list").execute("call-list", {}),
    /dataDir must be an absolute path/,
  );
});
