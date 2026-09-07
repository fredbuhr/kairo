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

test("llm_output attributes usage through cron job id and final snapshot overrides totals", async () => {
  const { dataDir, job } = await setup();
  try {
    const runtime = fakeApi(dataDir);
    assert.ok(runtime.hooks.has("llm_output"));
    assert.ok(runtime.hooks.has("after_tool_call"));
    assert.ok(runtime.hooks.has("reply_payload_sending"));

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
      { jobId: "cron_hook_123", runId: "run-hook-1" },
    );

    await runtime.emit(
      "after_tool_call",
      {
        runId: "run-hook-1",
        toolName: "kairo_project_get",
        durationMs: 20,
      },
      { runId: "run-hook-1", toolName: "kairo_project_get" },
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
        usage: { input: 12, output: 7, cacheRead: 30, total: 49 },
        turnUsd: 0.0042,
        durationMs: 200,
        fallbackUsed: false,
      },
    });

    const usage = await new KairoJobUsageLedger({ dataDir }).getUsage("ztikix", job.id);
    assert.equal(usage.summary.runs, 1);
    assert.equal(usage.summary.model_calls, 1);
    assert.equal(usage.summary.tool_calls, 1);
    assert.deepEqual(usage.summary.usage, { input: 12, output: 7, cacheRead: 30, total: 49 });
    assert.equal(usage.summary.known_cost_usd, 0.0042);
    assert.equal(usage.summary.cost_complete, true);
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
