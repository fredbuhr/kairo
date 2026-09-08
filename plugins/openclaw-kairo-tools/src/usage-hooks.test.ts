import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { KairoJobLedger, KairoJobUsageLedger, KairoStore } from "@kairo/core";
import { registerKairoUsageHooks } from "./usage-hooks.js";

async function setup() {
  const dataDir = await mkdtemp(path.join(os.tmpdir(), "kairo-usage-hooks-"));
  const store = new KairoStore({ dataDir });
  const jobs = new KairoJobLedger({ dataDir });
  await store.createProject({ name: "ZTIKIX" });
  const job = await jobs.createJob({
    project: "ztikix",
    title: "Hook usage proof",
    instructions: "Capture usage from a scheduled run.",
  });
  await jobs.linkScheduler("ztikix", job.id, {
    schedulerId: "cron_hook_123",
    schedulerTag: "kairo-bg-ztikix-hook",
  });
  return { dataDir, job };
}

function fakeApi(dataDir: string) {
  const hooks = new Map<string, Array<(event: any, ctx: any) => Promise<void> | void>>();
  const api = {
    pluginConfig: { dataDir },
    on(name: string, handler: (event: any, ctx: any) => Promise<void> | void) {
      const handlers = hooks.get(name) ?? [];
      handlers.push(handler);
      hooks.set(name, handlers);
    },
  };
  registerKairoUsageHooks(api as any);
  return {
    hooks,
    async emit(name: string, event: any, ctx: any = {}) {
      for (const handler of hooks.get(name) ?? []) await handler(event, ctx);
    },
  };
}

test("cron turn binds before Codex, preserves call identities, and uses final snapshot when available", async () => {
  const { dataDir, job } = await setup();
  try {
    const runtime = fakeApi(dataDir);
    assert.ok(runtime.hooks.has("before_agent_reply"));
    assert.ok(runtime.hooks.has("model_call_started"));
    assert.ok(runtime.hooks.has("model_call_ended"));
    assert.ok(runtime.hooks.has("llm_output"));
    assert.ok(runtime.hooks.has("after_tool_call"));
    assert.ok(runtime.hooks.has("reply_payload_sending"));

    await runtime.emit(
      "before_agent_reply",
      { cleanedBody: "[KAIRO BACKGROUND WORK]" },
      {
        trigger: "cron",
        runId: "run-hook-1",
        jobId: "cron_hook_123",
        sessionId: "session-hook-1",
      },
    );

    await runtime.emit("model_call_started", {
      runId: "run-hook-1",
      callId: "call-hook-1",
      sessionId: "session-hook-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      api: "responses",
      transport: "app-server",
      contextTokenBudget: 258400,
    });
    await runtime.emit("model_call_ended", {
      runId: "run-hook-1",
      callId: "call-hook-1",
      sessionId: "session-hook-1",
      provider: "openai",
      model: "gpt-5.6-luna",
      api: "responses",
      transport: "app-server",
      durationMs: 180,
      outcome: "completed",
      requestPayloadBytes: 1200,
      responseStreamBytes: 800,
      timeToFirstByteMs: 70,
    });

    await runtime.emit(
      "llm_output",
      {
        runId: "run-hook-1",
        sessionId: "session-hook-1",
        provider: "openai",
        model: "gpt-5.6-luna",
        resolvedRef: "openai/gpt-5.6-luna",
        harnessId: "codex",
        usage: { input: 10, output: 5, total: 15 },
        assistantTexts: [],
      },
      { runId: "run-hook-1" },
    );

    await runtime.emit(
      "after_tool_call",
      {
        runId: "run-hook-1",
        toolCallId: "tool-hook-1",
        toolName: "kairo_project_get",
        params: { project: "ztikix" },
        durationMs: 20,
      },
      { runId: "run-hook-1", toolName: "kairo_project_get", toolCallId: "tool-hook-1" },
    );
    await runtime.emit(
      "after_tool_call",
      {
        runId: "run-hook-1",
        toolCallId: "tool-hook-1",
        toolName: "kairo_project_get",
        params: { project: "ztikix" },
        durationMs: 20,
      },
      { runId: "run-hook-1", toolName: "kairo_project_get", toolCallId: "tool-hook-1" },
    );

    await runtime.emit("reply_payload_sending", {
      runId: "run-hook-1",
      payload: { text: "done" },
      kind: "final",
      usageState: {
        sessionId: "session-hook-1",
        provider: "openai",
        model: "gpt-5.6-luna",
        resolvedRef: "openai/gpt-5.6-luna",
        requested: "openai/gpt-5.6-luna",
        usage: { input: 12, output: 7, cacheRead: 30, total: 49 },
        turnUsd: 0.0042,
        durationMs: 200,
        fallbackUsed: false,
      },
    });

    const recorded = await new KairoJobUsageLedger({ dataDir }).getUsage("ztikix", job.id);
    assert.equal(recorded.summary.schema_version, 2);
    assert.equal(recorded.summary.runs, 1);
    assert.equal(recorded.summary.model_calls, 1);
    assert.equal(recorded.summary.usage_observations, 1);
    assert.equal(recorded.summary.tool_calls, 1);
    assert.deepEqual(recorded.summary.usage, { input: 12, output: 7, cacheRead: 30, total: 49 });
    assert.deepEqual(recorded.summary.usage_sources, ["final_snapshot"]);
    assert.equal(recorded.summary.usage_complete, true);
    assert.equal(recorded.summary.known_cost_usd, 0.0042);
    assert.equal(recorded.summary.cost_complete, true);
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
});

test("embedded Cron usage still persists without delivery snapshot or model-call hooks", async () => {
  const { dataDir, job } = await setup();
  try {
    const runtime = fakeApi(dataDir);

    await runtime.emit(
      "before_agent_reply",
      { cleanedBody: "[KAIRO BACKGROUND WORK]" },
      {
        trigger: "cron",
        runId: "embedded-run",
        jobId: "cron_hook_123",
        sessionId: "embedded-session",
      },
    );

    await runtime.emit(
      "after_tool_call",
      {
        runId: "embedded-run",
        toolCallId: "tool-start",
        toolName: "kairo_job_start",
        params: { project: "ztikix", jobId: job.id },
        durationMs: 11,
      },
      { runId: "embedded-run", toolName: "kairo_job_start", toolCallId: "tool-start" },
    );

    await runtime.emit(
      "llm_output",
      {
        runId: "embedded-run",
        sessionId: "embedded-session",
        provider: "openai",
        model: "gpt-5.6-luna",
        resolvedRef: "openai/gpt-5.6-luna",
        harnessId: "codex",
        usage: { input: 18, output: 650, cacheRead: 91130, cacheWrite: 19914, total: 111712 },
        assistantTexts: ["done"],
      },
      { runId: "embedded-run" },
    );

    await runtime.emit(
      "after_tool_call",
      {
        runId: "embedded-run",
        toolCallId: "tool-complete",
        toolName: "kairo_job_complete",
        params: { project: "ztikix", jobId: job.id, summary: "done" },
        durationMs: 13,
      },
      { runId: "embedded-run", toolName: "kairo_job_complete", toolCallId: "tool-complete" },
    );

    const recorded = await new KairoJobUsageLedger({ dataDir }).getUsage("ztikix", job.id);
    assert.equal(recorded.summary.runs, 1);
    assert.equal(recorded.summary.model_calls, 0);
    assert.equal(recorded.summary.usage_observations, 1);
    assert.equal(recorded.summary.tool_calls, 2);
    assert.deepEqual(recorded.summary.usage, {
      input: 18,
      output: 650,
      cacheRead: 91130,
      cacheWrite: 19914,
      total: 111712,
    });
    assert.deepEqual(recorded.summary.usage_sources, ["llm_output_observed"]);
    assert.equal(recorded.summary.usage_complete, false);
    assert.equal(recorded.summary.cost_complete, false);
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
});

test("kairo_job_start remains a fallback correlation anchor if outer Cron hook is unavailable", async () => {
  const { dataDir, job } = await setup();
  try {
    const runtime = fakeApi(dataDir);

    await runtime.emit(
      "after_tool_call",
      {
        runId: "fallback-run",
        toolCallId: "fallback-start",
        toolName: "kairo_job_start",
        params: { project: "ztikix", jobId: job.id },
        durationMs: 11,
      },
      { runId: "fallback-run", toolName: "kairo_job_start", toolCallId: "fallback-start" },
    );

    await runtime.emit(
      "llm_output",
      {
        runId: "fallback-run",
        sessionId: "fallback-session",
        provider: "openai",
        model: "gpt-5.6-luna",
        usage: { input: 2, output: 1, total: 3 },
        assistantTexts: [],
      },
      { runId: "fallback-run" },
    );

    const recorded = await new KairoJobUsageLedger({ dataDir }).getUsage("ztikix", job.id);
    assert.equal(recorded.summary.runs, 1);
    assert.equal(recorded.summary.usage_observations, 1);
    assert.equal(recorded.summary.tool_calls, 1);
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
});

test("non-cron model output is ignored", async () => {
  const { dataDir, job } = await setup();
  try {
    const runtime = fakeApi(dataDir);
    await runtime.emit(
      "llm_output",
      {
        runId: "ordinary-run",
        sessionId: "ordinary-session",
        provider: "openai",
        model: "gpt-5.6-luna",
        usage: { input: 2, output: 1, total: 3 },
        assistantTexts: [],
      },
      { runId: "ordinary-run" },
    );
    const usage = await new KairoJobUsageLedger({ dataDir }).getUsage("ztikix", job.id);
    assert.equal(usage.summary.runs, 0);
  } finally {
    await rm(dataDir, { recursive: true, force: true });
  }
});
