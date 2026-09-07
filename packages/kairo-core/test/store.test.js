import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { KairoError, KairoStore } from "../src/index.js";

async function withStore(fn) {
  const dataDir = await mkdtemp(path.join(os.tmpdir(), "kairo-core-"));
  const clock = () => new Date("2026-09-07T12:00:00.000Z");
  const store = new KairoStore({ dataDir, clock });
  try {
    return await fn(store, dataDir);
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
}

test("creates, nests, and lists human-readable projects", async () => {
  await withStore(async (store, dataDir) => {
    const parent = await store.createProject({ name: "Digital products", summary: "Portfolio domain" });
    const project = await store.createProject({ name: "ZTIKIX", summary: "Reaction brand", parent: "digital-products" });
    assert.equal(project.slug, "ztikix");
    assert.equal(project.type, "project");
    assert.equal(project.status, "active");
    assert.equal(project.parent_id, parent.id);

    const projects = await store.listProjects();
    assert.equal(projects.length, 2);

    const markdown = await readFile(path.join(dataDir, "projects", "ztikix", "project.md"), "utf8");
    assert.match(markdown, /^---\n/);
    assert.match(markdown, /type: "project"/);
    assert.match(markdown, /parent_slug: "digital-products"/);
    assert.match(markdown, /# ZTIKIX/);
  });
});

test("refuses duplicate project slugs", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "ZTIKIX" });
    await assert.rejects(
      store.createProject({ name: "Ztikix!" }),
      (error) => error instanceof KairoError && error.code === "PROJECT_EXISTS",
    );
  });
});

test("captures an idea without turning it into a decision", async () => {
  await withStore(async (store, dataDir) => {
    const project = await store.createProject({ name: "ZTIKIX" });
    const idea = await store.captureIdea({
      project: "ZTIKIX",
      title: "Rage Bait reaction",
      content: "Explore a reaction around rage bait.",
      rationale: "The expression fits internet culture.",
      epistemicStatus: "hypothesis",
      sourceKind: "conversation",
      sourceSession: "session-123",
      originalText: "Je pense qu'on pourrait faire un sticker Rage Bait.",
    });

    assert.match(idea.id, /^idea_/);
    assert.equal(idea.type, "idea");
    assert.equal(idea.project_id, project.id);
    assert.equal(idea.epistemic_status, "hypothesis");

    const stored = await store.getIdea("ztikix", idea.id);
    assert.equal(stored.type, "idea");
    assert.equal(stored.project_slug, "ztikix");
    assert.match(stored.body, /## Idea/);
    assert.match(stored.body, /## Original wording/);

    const markdown = await readFile(path.join(dataDir, "projects", "ztikix", "ideas", `${idea.id}.md`), "utf8");
    assert.doesNotMatch(markdown, /type: "decision"/);
  });
});

test("isolates ideas by project", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "ZTIKIX" });
    await store.createProject({ name: "Aventulire" });
    await store.captureIdea({ project: "ztikix", title: "One", content: "First" });
    await store.captureIdea({ project: "aventulire", title: "Two", content: "Second" });

    const ztikixIdeas = await store.listIdeas("ztikix");
    assert.equal(ztikixIdeas.length, 1);
    assert.equal(ztikixIdeas[0].project_slug, "ztikix");
  });
});

test("stores decisions separately from ideas", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "KAIRO" });
    const decision = await store.recordDecision({
      project: "kairo",
      title: "API-first V0",
      statement: "Use external model APIs in V0.",
      rationale: "Reduce server complexity while preserving a local-provider adapter for later.",
      alternatives: ["Run a local model immediately"],
      consequences: "Provider routing must remain model-agnostic.",
      confidence: 0.9,
    });
    assert.equal(decision.type, "decision");
    const stored = await store.getDecision("kairo", decision.id);
    assert.match(stored.body, /## Decision/);
  });
});

test("requires an epistemic status for knowledge claims", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "Crypto" });
    const claim = await store.captureKnowledgeClaim({
      project: "crypto",
      title: "Market hypothesis",
      claim: "This catalyst may increase volatility.",
      epistemicStatus: "hypothesis",
      confidence: 0.55,
    });
    assert.equal(claim.epistemic_status, "hypothesis");

    await assert.rejects(
      store.captureKnowledgeClaim({
        project: "crypto",
        title: "Bad claim",
        claim: "Unsupported certainty",
        epistemicStatus: "certain",
      }),
      /Invalid epistemic status/,
    );
  });
});

test("tasks require an explicit authority ceiling", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "ZTIKIX" });
    const task = await store.createTask({
      project: "ztikix",
      title: "Draft social post",
      owner: "kairo",
      authorityCeiling: "A2",
      budget: 0.25,
    });
    assert.equal(task.authority_ceiling, "A2");
    assert.equal(task.owner, "kairo");

    await assert.rejects(
      store.createTask({
        project: "ztikix",
        title: "Unsafe task",
        authorityCeiling: "admin",
      }),
      /Invalid authority ceiling/,
    );
  });
});

test("sources are durable first-class records", async () => {
  await withStore(async (store) => {
    await store.createProject({ name: "Aventulire" });
    const source = await store.captureSource({
      project: "aventulire",
      title: "Competitor page",
      kind: "url",
      locator: "https://example.test/competitor",
      summary: "Research input",
    });
    const stored = await store.getSource("aventulire", source.id);
    assert.equal(stored.kind, "url");
    assert.match(stored.body, /https:\/\/example\.test\/competitor/);
  });
});

test("unknown project fails explicitly", async () => {
  await withStore(async (store) => {
    await assert.rejects(
      store.captureIdea({ project: "missing", title: "Idea", content: "Body" }),
      (error) => error instanceof KairoError && error.code === "PROJECT_NOT_FOUND",
    );
  });
});
