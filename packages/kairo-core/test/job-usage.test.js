import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { KairoJobLedger, KairoJobUsageLedger, KairoStore } from "../src/index.js";

async function withUsage(fn) {
  const dataDir = await mkdtemp(path.join(os.tmpdir(), "kairo-job-usage-"));
  let tick = 0;
  const clock = () => new Date(Date.parse("2026-09-08T00:00:00.000Z") + tick++ * 1000);
  const store = new KairoStore({ dataDir, clock });
  const jobs = new KairoJobLedger({ dataDir, clock });
  const usage = new KairoJobUsageLedger({ dataDir, clock });
  try {
    await store.createProject({ name: "ZTIKIX" });
    const job = await jobs.createJob({
      project: "ztikix",
      title: "Usage proof",
      instructions: "Measure model usage.",
      requestedBudget: 1,
    });
    await jobs.linkScheduler("ztikix", job.id, {
      schedulerId: "cron_usage_123",
      schedulerTag: "kairo-bg-ztikix-usage",
    });
    return await fn({ dataDir, job, jobs, usage });
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
}

test("finds a KAIRO job from its authoritative scheduler id", async () => {
  await withUsage(async ({ job, usage }) => {
    assert.deepEqual(await usage.findJobBySchedulerId("cron_usage_123"), {
      project_slug: "ztikix",
      job_id: job.id,
      scheduler_id: "cron_usage_123",
    });
    assert.equal(await usage.findJobBySchedulerId("cron_missing"), null);
  });
});

test("persists per-call model usage and tool telemetry beside the job", async () => {
  await withUsage(async ({ dataDir, job, usage }) => {
    await usage.recordLlmOutputBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      harnessId: "codex",
      usage: { input: 10, output: 4, cacheRead: 20, total: 34 },
    });
    await usage.recordToolCallBySchedulerId("cron_usage_123", {
      runId: "run-1",
      toolName: "kairo_project_get",
      durationMs: 12,
    });
    await usage.recordLlmOutputBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      usage: { input: 5, output: 6, cacheWrite: 8, total: 19 },
    });

    const result = await usage.getUsage("ztikix", job.id);
    assert.equal(result.summary.runs, 1);
    assert.equal(result.summary.model_calls, 2);
    assert.equal(result.summary.tool_calls, 1);
    assert.deepEqual(result.summary.provider_models, ["openai/gpt-5.6-luna"]);
    assert.deepEqual(result.summary.usage, {
      input: 15,
      output: 10,
      cacheRead: 20,
      cacheWrite: 8,
      total: 53,
    });
    assert.equal(result.summary.cost_complete, false);

    const raw = JSON.parse(
      await readFile(path.join(dataDir, "projects", "ztikix", "job-usage", `${job.id}.json`), "utf8"),
    );
    assert.equal(raw.job_id, job.id);
    assert.equal(raw.scheduler_id, "cron_usage_123");
    assert.equal(raw.runs[0].calls.length, 2);
    assert.equal(raw.runs[0].tool_calls[0].tool_name, "kairo_project_get");
  });
});

test("final turn snapshot becomes the authoritative aggregate and records known cost", async () => {
  await withUsage(async ({ job, usage }) => {
    await usage.recordLlmOutputBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      usage: { input: 10, output: 5, total: 15 },
    });
    await usage.recordLlmOutputBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      usage: { input: 7, output: 3, total: 10 },
    });

    await usage.recordFinalSnapshotBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      usage: { input: 20, output: 9, cacheRead: 100, total: 129 },
      turnUsd: 0.0123,
      durationMs: 2500,
      fallbackUsed: false,
    });

    const result = await usage.getUsage("ztikix", job.id);
    assert.equal(result.summary.model_calls, 2);
    assert.deepEqual(result.summary.usage, { input: 20, output: 9, cacheRead: 100, total: 129 });
    assert.equal(result.summary.known_cost_usd, 0.0123);
    assert.equal(result.summary.priced_runs, 1);
    assert.equal(result.summary.unpriced_runs, 0);
    assert.equal(result.summary.cost_complete, true);
  });
});
