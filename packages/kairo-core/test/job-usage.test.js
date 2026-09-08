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
      requestedBudgetUsd: 1,
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

test("persists run binding, route request, real model-call identities, usage observations, and deduplicated tools", async () => {
  await withUsage(async ({ dataDir, job, usage }) => {
    await usage.recordRunBindingBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      trigger: "cron",
    });

    const route = await usage.recordRouteRequestBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
    });
    assert.equal(route.disposition, "observed");
    assert.equal(route.routeRequest.requested_ref, "openai/gpt-5.6-luna");
    const duplicateRoute = await usage.recordRouteRequestBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "anthropic",
      model: "claude-opus-4-1",
    });
    assert.equal(duplicateRoute.disposition, "already_observed");
    assert.equal(duplicateRoute.routeRequest.requested_ref, "openai/gpt-5.6-luna");

    const started = await usage.recordModelCallStartedBySchedulerId("cron_usage_123", {
      runId: "run-1",
      callId: "call-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      api: "responses",
      transport: "app-server",
      contextTokenBudget: 258400,
    });
    assert.equal(started.disposition, "started");
    const duplicateStart = await usage.recordModelCallStartedBySchedulerId("cron_usage_123", {
      runId: "run-1",
      callId: "call-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
    });
    assert.equal(duplicateStart.disposition, "already_observed");

    const ended = await usage.recordModelCallEndedBySchedulerId("cron_usage_123", {
      runId: "run-1",
      callId: "call-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      durationMs: 250,
      outcome: "completed",
      requestPayloadBytes: 1200,
      responseStreamBytes: 900,
      timeToFirstByteMs: 80,
    });
    assert.equal(ended.disposition, "ended");
    const duplicateEnd = await usage.recordModelCallEndedBySchedulerId("cron_usage_123", {
      runId: "run-1",
      callId: "call-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      durationMs: 999,
      outcome: "completed",
    });
    assert.equal(duplicateEnd.disposition, "already_ended");

    await usage.recordUsageObservationBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      harnessId: "codex",
      usage: { input: 10, output: 4, cacheRead: 20, total: 34 },
    });

    const tool = await usage.recordToolCallBySchedulerId("cron_usage_123", {
      runId: "run-1",
      toolCallId: "tool-1",
      toolName: "kairo_project_get",
      durationMs: 12,
    });
    assert.equal(tool.disposition, "observed");
    const duplicateTool = await usage.recordToolCallBySchedulerId("cron_usage_123", {
      runId: "run-1",
      toolCallId: "tool-1",
      toolName: "kairo_project_get",
      durationMs: 12,
    });
    assert.equal(duplicateTool.disposition, "already_observed");

    const result = await usage.getUsage("ztikix", job.id);
    assert.equal(result.summary.schema_version, 3);
    assert.equal(result.summary.runs, 1);
    assert.equal(result.summary.model_calls, 1);
    assert.equal(result.summary.usage_observations, 1);
    assert.equal(result.summary.tool_calls, 1);
    assert.deepEqual(result.summary.provider_models, ["openai/gpt-5.6-luna"]);
    assert.deepEqual(result.summary.harnesses, ["codex"]);
    assert.deepEqual(result.summary.usage, { input: 10, output: 4, cacheRead: 20, total: 34 });
    assert.deepEqual(result.summary.usage_sources, ["llm_output_observed"]);
    assert.equal(result.summary.usage_complete, false);
    assert.equal(result.summary.cost_complete, false);
    assert.equal(result.summary.routing_complete, false);
    assert.equal(result.summary.routing.length, 1);
    assert.deepEqual(result.summary.routing[0], {
      run_id: "run-1",
      classification: "observed_match",
      reason_code: "final_snapshot_missing",
      reason: "The pre-run requested route matches the observed route, but no authoritative final routing snapshot was delivered.",
      complete: false,
      requested_ref: "openai/gpt-5.6-luna",
      resolved_ref: "openai/gpt-5.6-luna",
      harness_ids: ["codex"],
      observed_refs: ["openai/gpt-5.6-luna"],
      evidence_sources: ["before_agent_reply", "llm_output", "model_call"],
    });

    const raw = JSON.parse(
      await readFile(path.join(dataDir, "projects", "ztikix", "job-usage", `${job.id}.json`), "utf8"),
    );
    assert.equal(raw.schema_version, 3);
    assert.equal(raw.job_id, job.id);
    assert.equal(raw.scheduler_id, "cron_usage_123");
    assert.equal(raw.runs[0].route_request.requested_ref, "openai/gpt-5.6-luna");
    assert.equal(raw.runs[0].model_calls.length, 1);
    assert.equal(raw.runs[0].model_calls[0].call_id, "call-1");
    assert.equal(raw.runs[0].usage_observations.length, 1);
    assert.equal(raw.runs[0].tool_calls.length, 1);
    assert.equal(raw.runs[0].tool_calls[0].tool_call_id, "tool-1");
  });
});

test("final turn snapshot is authoritative for aggregate usage, known cost, and direct routing", async () => {
  await withUsage(async ({ job, usage }) => {
    await usage.recordRunBindingBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      trigger: "cron",
    });
    await usage.recordRouteRequestBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
    });
    await usage.recordUsageObservationBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      harnessId: "codex",
      usage: { input: 10, output: 5, total: 15 },
    });
    await usage.recordUsageObservationBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      harnessId: "codex",
      usage: { input: 7, output: 3, total: 10 },
    });

    await usage.recordFinalSnapshotBySchedulerId("cron_usage_123", {
      runId: "run-1",
      sessionId: "session-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      requested: "openai/gpt-5.6-luna",
      usage: { input: 20, output: 9, cacheRead: 100, total: 129 },
      turnUsd: 0.0123,
      durationMs: 2500,
      fallbackUsed: false,
      authMode: "oauth",
      reasoningEffort: "medium",
      fastMode: false,
      contextTokenBudget: 272000,
    });

    const result = await usage.getUsage("ztikix", job.id);
    assert.equal(result.summary.model_calls, 0);
    assert.equal(result.summary.usage_observations, 2);
    assert.deepEqual(result.summary.usage, { input: 20, output: 9, cacheRead: 100, total: 129 });
    assert.deepEqual(result.summary.usage_sources, ["final_snapshot"]);
    assert.equal(result.summary.usage_complete, true);
    assert.equal(result.summary.known_cost_usd, 0.0123);
    assert.equal(result.summary.priced_runs, 1);
    assert.equal(result.summary.unpriced_runs, 0);
    assert.equal(result.summary.cost_complete, true);
    assert.equal(result.summary.routing_complete, true);
    assert.equal(result.summary.routing[0].classification, "requested");
    assert.equal(result.summary.routing[0].reason_code, "requested_equals_resolved");
    assert.equal(result.summary.routing[0].requested_ref, "openai/gpt-5.6-luna");
    assert.equal(result.summary.routing[0].resolved_ref, "openai/gpt-5.6-luna");
    assert.equal(result.summary.routing[0].fallback_used, false);
    assert.equal(result.summary.routing[0].auth_mode, "oauth");
    assert.deepEqual(result.summary.routing[0].harness_ids, ["codex"]);
  });
});

test("classifies session overrides, fallbacks, and unexplained resolved differences without guessing", async () => {
  await withUsage(async ({ job, usage }) => {
    await usage.recordFinalSnapshotBySchedulerId("cron_usage_123", {
      runId: "override-run",
      sessionId: "session-override",
      provider: "openai",
      model: "gpt-5.6-sol",
      resolvedRef: "openai/gpt-5.6-sol",
      requested: "openai/gpt-5.6-sol",
      fallbackUsed: false,
      overrideSource: "user",
    });
    await usage.recordFinalSnapshotBySchedulerId("cron_usage_123", {
      runId: "fallback-run",
      sessionId: "session-fallback",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      requested: "anthropic/claude-opus-4-1",
      fallbackUsed: true,
    });
    await usage.recordFinalSnapshotBySchedulerId("cron_usage_123", {
      runId: "difference-run",
      sessionId: "session-difference",
      provider: "openai",
      model: "gpt-5.6-luna",
      resolvedRef: "openai/gpt-5.6-luna",
      requested: "openai/gpt-5.6-luna-alias",
      fallbackUsed: false,
    });

    const result = await usage.getUsage("ztikix", job.id);
    const byRun = new Map(result.summary.routing.map((route) => [route.run_id, route]));

    assert.equal(byRun.get("override-run").classification, "session_override");
    assert.equal(byRun.get("override-run").reason_code, "session_override");
    assert.equal(byRun.get("override-run").override_source, "user");

    assert.equal(byRun.get("fallback-run").classification, "fallback");
    assert.equal(byRun.get("fallback-run").reason_code, "fallback_used");
    assert.equal(byRun.get("fallback-run").fallback_used, true);

    assert.equal(byRun.get("difference-run").classification, "resolved_difference");
    assert.equal(byRun.get("difference-run").reason_code, "requested_resolved_mismatch_without_fallback");
    assert.match(byRun.get("difference-run").reason, /without inventing its cause/);
    assert.equal(result.summary.routing_complete, true);
  });
});
