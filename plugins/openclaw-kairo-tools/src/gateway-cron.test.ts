import assert from "node:assert/strict";
import test from "node:test";
import { createGatewayCronBridge } from "./gateway-cron.js";

test("Gateway Cron bridge persists the exact KAIRO toolsAllow cap", async () => {
  const adds: any[] = [];
  const bridge = createGatewayCronBridge();
  const cron = {
    async add(input: any) {
      adds.push(input);
      return { id: "cron_tool_cap" };
    },
    async remove() {
      return { removed: true };
    },
  };
  await bridge.service.start({
    config: {},
    stateDir: "/tmp/kairo-test",
    logger: { debug() {}, info() {}, warn() {}, error() {} },
    getCron: () => cron as any,
  } as any);

  try {
    const toolsAllow = [
      "kairo_job_start",
      "kairo_project_get",
      "kairo_job_complete",
      "kairo_job_fail",
    ];
    const handle = await bridge.scheduleAgentTurn({
      sessionKey: "agent:main:session:test",
      agentId: "main",
      at: new Date("2030-01-02T01:00:00.000Z"),
      name: "Tool cap proof",
      tag: "kairo-bg-ztikix-test",
      message: "Read the project.",
      announce: false,
      toolsAllow,
    });

    assert.equal(handle.id, "cron_tool_cap");
    assert.equal(adds.length, 1);
    assert.deepEqual(adds[0].payload.toolsAllow, toolsAllow);
    assert.notEqual(adds[0].payload.toolsAllow, toolsAllow);
    assert.equal(adds[0].payload.toolsAllow.includes("exec"), false);
    assert.equal(adds[0].payload.toolsAllow.includes("message"), false);
  } finally {
    await bridge.service.stop?.({} as any);
  }
});

test("Gateway Cron bridge fails closed when no exact runtime cap is supplied by its caller type", async () => {
  const bridge = createGatewayCronBridge();
  await bridge.service.start({
    config: {},
    stateDir: "/tmp/kairo-test",
    logger: { debug() {}, info() {}, warn() {}, error() {} },
    getCron: () => ({
      async add(input: any) {
        assert.ok(Array.isArray(input.payload.toolsAllow));
        return { id: "cron_empty_cap" };
      },
      async remove() {
        return { removed: true };
      },
    }) as any,
  } as any);

  try {
    const handle = await bridge.scheduleAgentTurn({
      sessionKey: "agent:main:session:test",
      at: new Date("2030-01-02T01:00:00.000Z"),
      name: "Deny-all proof",
      tag: "kairo-bg-ztikix-deny-all",
      message: "No tools should be exposed.",
      announce: false,
      toolsAllow: [],
    });
    assert.equal(handle.id, "cron_empty_cap");
  } finally {
    await bridge.service.stop?.({} as any);
  }
});
