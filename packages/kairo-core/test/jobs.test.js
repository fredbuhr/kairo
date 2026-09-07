import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { KairoError, KairoJobLedger, KairoStore } from "../src/index.js";

async function withLedger(fn) {
  const dataDir = await mkdtemp(path.join(os.tmpdir(), "kairo-job-ledger-"));
  let tick = 0;
  const clock = () => new Date(Date.parse("2026-09-07T12:00:00.000Z") + tick++ * 1000);
  const store = new KairoStore({ dataDir, clock });
  const ledger = new KairoJobLedger({ dataDir, clock });
  try {
    await store.createProject({ name: "ZTIKIX" });
    return await fn({ ledger, store, dataDir });
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
}

async function createRunningJob(ledger, title = "Checkpoint test") {
  const job = await ledger.createJob({
    project: "ztikix",
    title,
    instructions: "Run a replay-sensitive internal step.",
  });
  await ledger.linkScheduler("ztikix", job.id, {
    schedulerId: "cron_123",
    schedulerTag: "kairo-bg-ztikix-test",
  });
  return await ledger.markRunning("ztikix", job.id);
}

test("persists scheduling intent before an external scheduler is linked", async () => {
  await withLedger(async ({ ledger, dataDir }) => {
    const job = await ledger.createJob({
      project: "ztikix",
      title: "Overnight research",
      instructions: "Compare relevant public signals.",
      authorityCeiling: "A2",
      scheduledFor: "2026-09-08T01:00:00.000Z",
      requestedBudget: 0.5,
      sourceSession: "session-123",
    });

    assert.match(job.id, /^job_/);
    assert.equal(job.status, "scheduling");
    assert.equal(job.authority_ceiling, "A2");
    assert.equal(job.requested_budget, 0.5);
    assert.equal(job.budget_enforced, false);

    const markdown = await readFile(
      path.join(dataDir, "projects", "ztikix", "jobs", `${job.id}.md`),
      "utf8",
    );
    assert.match(markdown, /status: "scheduling"/);
    assert.match(markdown, /## Instructions/);
  });
});

test("links scheduler state and records a complete execution lifecycle", async () => {
  await withLedger(async ({ ledger }) => {
    const job = await ledger.createJob({
      project: "ztikix",
      title: "Overnight research",
      instructions: "Research and report.",
    });

    const queued = await ledger.linkScheduler("ztikix", job.id, {
      schedulerId: "cron_123",
      schedulerTag: "kairo-bg-ztikix-test",
    });
    assert.equal(queued.status, "queued");
    assert.equal(queued.scheduler_id, "cron_123");

    const running = await ledger.markRunning("ztikix", job.id);
    assert.equal(running.status, "running");
    assert.ok(running.started_at);

    const completed = await ledger.completeJob("ztikix", job.id, {
      summary: "Research completed with two supported findings.",
    });
    assert.equal(completed.status, "completed");
    assert.match(completed.body, /## Completion summary/);
    assert.match(completed.body, /two supported findings/);

    const listed = await ledger.listJobs("ztikix");
    assert.equal(listed.length, 1);
    assert.equal(listed[0].status, "completed");
  });
});

test("records scheduler failure durably", async () => {
  await withLedger(async ({ ledger }) => {
    const job = await ledger.createJob({
      project: "ztikix",
      title: "Failed scheduling",
      instructions: "This job will fail before running.",
    });
    const failed = await ledger.failJob("ztikix", job.id, { reason: "Scheduler unavailable." });
    assert.equal(failed.status, "failed");
    assert.match(failed.body, /Scheduler unavailable/);
  });
});

test("rejects invalid lifecycle transitions", async () => {
  await withLedger(async ({ ledger }) => {
    const job = await ledger.createJob({
      project: "ztikix",
      title: "Transition test",
      instructions: "Validate lifecycle rules.",
    });
    await ledger.linkScheduler("ztikix", job.id, {
      schedulerId: "cron_123",
      schedulerTag: "kairo-bg-ztikix-test",
    });
    await ledger.markRunning("ztikix", job.id);
    await ledger.completeJob("ztikix", job.id, { summary: "Done." });

    await assert.rejects(
      ledger.markRunning("ztikix", job.id),
      (error) => error instanceof KairoError && error.code === "INVALID_JOB_TRANSITION",
    );
  });
});

test("durably starts a replay checkpoint and does not duplicate the same step key", async () => {
  await withLedger(async ({ ledger, dataDir }) => {
    const running = await createRunningJob(ledger);

    const first = await ledger.beginStep("ztikix", running.id, {
      stepKey: "write:trend-source",
      description: "Persist one source record after the lookup succeeds.",
    });
    assert.equal(first.disposition, "started");
    assert.equal(first.step.status, "started");
    assert.equal(first.job.execution_steps.length, 1);

    const replay = await ledger.beginStep("ztikix", running.id, {
      stepKey: "write:trend-source",
      description: "This description must not create a duplicate checkpoint.",
    });
    assert.equal(replay.disposition, "already_started");
    assert.equal(replay.job.execution_steps.length, 1);
    assert.equal(replay.step.description, "Persist one source record after the lookup succeeds.");

    const markdown = await readFile(
      path.join(dataDir, "projects", "ztikix", "jobs", `${running.id}.md`),
      "utf8",
    );
    assert.match(markdown, /execution_steps:/);
    assert.match(markdown, /## Execution checkpoints/);
    assert.match(markdown, /write:trend-source/);
  });
});

test("blocks job completion while a checkpoint outcome is unresolved", async () => {
  await withLedger(async ({ ledger }) => {
    const running = await createRunningJob(ledger, "Unresolved checkpoint");
    await ledger.beginStep("ztikix", running.id, {
      stepKey: "write:knowledge-claim",
      description: "Persist one knowledge claim.",
    });

    await assert.rejects(
      ledger.completeJob("ztikix", running.id, { summary: "Should not close yet." }),
      (error) => error instanceof KairoError && error.code === "UNRESOLVED_JOB_STEPS",
    );

    const current = await ledger.getJob("ztikix", running.id);
    assert.equal(current.status, "running");
    assert.equal(current.execution_steps[0].status, "started");
  });
});

test("completes a checkpoint idempotently before allowing job completion", async () => {
  await withLedger(async ({ ledger }) => {
    const running = await createRunningJob(ledger, "Completed checkpoint");
    await ledger.beginStep("ztikix", running.id, {
      stepKey: "write:knowledge-claim",
      description: "Persist one knowledge claim.",
    });

    const completedStep = await ledger.completeStep("ztikix", running.id, {
      stepKey: "write:knowledge-claim",
      summary: "Knowledge claim persisted with a stable ID.",
    });
    assert.equal(completedStep.disposition, "completed");
    assert.equal(completedStep.step.status, "completed");
    assert.ok(completedStep.step.completed_at);

    const duplicateCompletion = await ledger.completeStep("ztikix", running.id, {
      stepKey: "write:knowledge-claim",
      summary: "A retry must not overwrite the original checkpoint.",
    });
    assert.equal(duplicateCompletion.disposition, "already_completed");
    assert.equal(duplicateCompletion.step.summary, "Knowledge claim persisted with a stable ID.");

    const replayBegin = await ledger.beginStep("ztikix", running.id, {
      stepKey: "write:knowledge-claim",
    });
    assert.equal(replayBegin.disposition, "already_completed");

    const completedJob = await ledger.completeJob("ztikix", running.id, {
      summary: "All replay-sensitive work completed.",
    });
    assert.equal(completedJob.status, "completed");
    assert.equal(completedJob.execution_steps.length, 1);
    assert.equal(completedJob.execution_steps[0].status, "completed");
  });
});

test("rejects checkpoint writes outside a running job", async () => {
  await withLedger(async ({ ledger }) => {
    const job = await ledger.createJob({
      project: "ztikix",
      title: "Queued checkpoint",
      instructions: "Do not allow step state before execution starts.",
    });
    await ledger.linkScheduler("ztikix", job.id, {
      schedulerId: "cron_queued",
      schedulerTag: "kairo-bg-ztikix-queued",
    });

    await assert.rejects(
      ledger.beginStep("ztikix", job.id, { stepKey: "write:too-early" }),
      (error) => error instanceof KairoError && error.code === "INVALID_JOB_STEP_STATE",
    );
  });
});

test("job ledger remains project-isolated", async () => {
  await withLedger(async ({ ledger, store }) => {
    await store.createProject({ name: "Aventulire" });
    const ztikixJob = await ledger.createJob({
      project: "ztikix",
      title: "ZTIKIX research",
      instructions: "ZTIKIX only.",
    });
    await ledger.createJob({
      project: "aventulire",
      title: "Aventulire research",
      instructions: "Aventulire only.",
    });

    const ztikix = await ledger.listJobs("ztikix");
    assert.equal(ztikix.length, 1);
    assert.equal(ztikix[0].id, ztikixJob.id);
  });
});
