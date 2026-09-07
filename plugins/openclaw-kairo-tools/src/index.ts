import { randomUUID } from "node:crypto";
import path from "node:path";
import { KairoStore, type KairoRecord } from "@kairo/core";
import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

const projectStatus = Type.Union([
  Type.Literal("inbox"),
  Type.Literal("incubation"),
  Type.Literal("active"),
  Type.Literal("waiting"),
  Type.Literal("paused"),
  Type.Literal("completed"),
  Type.Literal("archived"),
]);

const epistemicStatus = Type.Union([
  Type.Literal("fact"),
  Type.Literal("hypothesis"),
  Type.Literal("deduction"),
  Type.Literal("opinion"),
  Type.Literal("unknown"),
]);

const sourceKind = Type.Union([
  Type.Literal("url"),
  Type.Literal("document"),
  Type.Literal("dataset"),
  Type.Literal("conversation"),
  Type.Literal("note"),
  Type.Literal("other"),
]);

const backgroundAuthority = Type.Union([
  Type.Literal("A0"),
  Type.Literal("A1"),
  Type.Literal("A2"),
]);

const configSchema = Type.Object(
  {
    dataDir: Type.String({
      minLength: 1,
      description: "Absolute path to KAIRO runtime-private domain data.",
    }),
  },
  { additionalProperties: false },
);

const backgroundScheduleParameters = Type.Object(
  {
    project: Type.String({ minLength: 1, description: "Existing KAIRO project slug or name." }),
    title: Type.String({ minLength: 1, description: "Concise background-work title." }),
    instructions: Type.String({ minLength: 1, description: "Work to perform during the future agent turn." }),
    at: Type.String({
      minLength: 1,
      description: "Absolute ISO-8601 date/time including Z or an explicit UTC offset, for example 2026-09-08T03:00:00+02:00.",
    }),
    authorityCeiling: Type.Optional(backgroundAuthority),
    announce: Type.Optional(
      Type.Boolean({ description: "When true (default), announce the result back to the session route after the scheduled turn." }),
    ),
  },
  { additionalProperties: false },
);

function storeFor(dataDir: string): KairoStore {
  if (!path.isAbsolute(dataDir)) {
    throw new Error("KAIRO plugin dataDir must be an absolute path.");
  }
  return new KairoStore({ dataDir });
}

function compact(record: KairoRecord): Record<string, unknown> {
  const { body: _body, ...metadata } = record;
  return metadata;
}

function parseAbsoluteSchedule(value: string): Date {
  const text = value.trim();
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(text)) {
    throw new TypeError("Background schedule must include Z or an explicit UTC offset.");
  }
  const timestamp = Date.parse(text);
  if (!Number.isFinite(timestamp)) throw new TypeError("Background schedule is not a valid ISO-8601 date/time.");
  return new Date(timestamp);
}

function backgroundPrompt(params: {
  project: string;
  title: string;
  instructions: string;
  authorityCeiling: "A0" | "A1" | "A2";
}): string {
  return [
    "[KAIRO BACKGROUND WORK]",
    `Project: ${params.project}`,
    `Title: ${params.title}`,
    `Authority ceiling: ${params.authorityCeiling}`,
    "",
    "Task:",
    params.instructions,
    "",
    "Operating rules:",
    "1. Re-read the relevant KAIRO project context before acting.",
    "2. Keep facts, hypotheses, deductions, opinions, and unknowns distinct.",
    "3. Never exceed the stated authority ceiling. This V0 background scheduler never grants A3+ external authority.",
    "4. Do not publish, send messages, purchase, trade, delete external data, or change external systems.",
    "5. Record useful evidence with kairo_source_capture and durable discrete findings with kairo_knowledge_capture when appropriate.",
    "6. If the task requires missing information or additional authority, stop and state the limitation explicitly.",
    "7. Return a concise completion report to the originating session when finished.",
  ].join("\n");
}

export default defineToolPlugin({
  id: "kairo-tools",
  name: "KAIRO Tools",
  description: "Durable KAIRO project, idea, research-memory, and bounded background-work tools.",
  configSchema,
  tools: (tool) => [
    tool({
      name: "kairo_project_create",
      label: "Create KAIRO Project",
      description:
        "Create a durable KAIRO project. Use only when the user intends to create a project/domain container; do not create a new project merely because an idea mentions a new topic.",
      parameters: Type.Object(
        {
          name: Type.String({ minLength: 1, description: "Human-readable project name." }),
          slug: Type.Optional(
            Type.String({ minLength: 1, description: "Optional stable project slug. KAIRO can derive it from the name." }),
          ),
          summary: Type.Optional(Type.String({ description: "Short factual project summary." })),
          status: Type.Optional(projectStatus),
          parent: Type.Optional(
            Type.String({ minLength: 1, description: "Optional existing parent project slug/name." }),
          ),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const project = await storeFor(config.dataDir).createProject(params);
        return { project: compact(project) };
      },
    }),
    tool({
      name: "kairo_project_list",
      label: "List KAIRO Projects",
      description:
        "List durable KAIRO projects with compact metadata. Use this to resolve the correct project before writing project-scoped knowledge.",
      parameters: Type.Object({}, { additionalProperties: false }),
      async execute(_params, config, context) {
        context.signal?.throwIfAborted();
        const projects = await storeFor(config.dataDir).listProjects();
        return { projects: projects.map(compact) };
      },
    }),
    tool({
      name: "kairo_project_get",
      label: "Get KAIRO Project",
      description: "Read one KAIRO project, including its human-readable Markdown body.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Project slug or name." }),
        },
        { additionalProperties: false },
      ),
      async execute({ project }, config, context) {
        context.signal?.throwIfAborted();
        return { project: await storeFor(config.dataDir).getProject(project) };
      },
    }),
    tool({
      name: "kairo_idea_capture",
      label: "Capture KAIRO Idea",
      description:
        "Persist an idea under an existing project. An idea is not a decision. Preserve uncertainty and the user's original wording when it matters; never promote a tentative statement to fact or decision.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Existing project slug or name." }),
          title: Type.String({ minLength: 1, description: "Concise idea title." }),
          content: Type.String({ minLength: 1, description: "Faithful description of the idea." }),
          rationale: Type.Optional(Type.String({ description: "Why the idea may be useful or relevant, if stated." })),
          epistemicStatus: Type.Optional(epistemicStatus),
          originalText: Type.Optional(
            Type.String({ description: "Exact user wording when available. Do not fabricate a quote." }),
          ),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const idea = await storeFor(config.dataDir).captureIdea({
          ...params,
          sourceKind: "openclaw",
        });
        return { idea: compact(idea) };
      },
    }),
    tool({
      name: "kairo_idea_list",
      label: "List KAIRO Ideas",
      description: "List ideas belonging to one KAIRO project without importing ideas from unrelated projects.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Project slug or name." }),
        },
        { additionalProperties: false },
      ),
      async execute({ project }, config, context) {
        context.signal?.throwIfAborted();
        const ideas = await storeFor(config.dataDir).listIdeas(project);
        return { ideas: ideas.map(compact) };
      },
    }),
    tool({
      name: "kairo_idea_get",
      label: "Get KAIRO Idea",
      description: "Read one durable idea, including its human-readable Markdown content and provenance metadata.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1, description: "Project slug or name." }),
          ideaId: Type.String({ minLength: 1, description: "Stable KAIRO idea ID." }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, ideaId }, config, context) {
        context.signal?.throwIfAborted();
        return { idea: await storeFor(config.dataDir).getIdea(project, ideaId) };
      },
    }),
    tool({
      name: "kairo_source_capture",
      label: "Capture KAIRO Source",
      description:
        "Persist a source/evidence reference under an existing project. Store the locator faithfully; do not invent a source or claim that a source supports more than it actually does.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          title: Type.String({ minLength: 1 }),
          kind: sourceKind,
          locator: Type.String({ minLength: 1, description: "URL, document identifier/path, dataset locator, or other faithful source locator." }),
          summary: Type.Optional(Type.String({ description: "Short source summary grounded in the source." })),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const source = await storeFor(config.dataDir).captureSource(params);
        return { source: compact(source) };
      },
    }),
    tool({
      name: "kairo_source_get",
      label: "Get KAIRO Source",
      description: "Read one durable project source/evidence record.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          sourceId: Type.String({ minLength: 1 }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, sourceId }, config, context) {
        context.signal?.throwIfAborted();
        return { source: await storeFor(config.dataDir).getSource(project, sourceId) };
      },
    }),
    tool({
      name: "kairo_knowledge_capture",
      label: "Capture KAIRO Knowledge",
      description:
        "Persist one discrete knowledge claim with an explicit epistemic status. Use fact only when reliable available evidence supports the claim; otherwise choose hypothesis, deduction, opinion, or unknown.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          title: Type.String({ minLength: 1 }),
          claim: Type.String({ minLength: 1 }),
          epistemicStatus,
          confidence: Type.Optional(Type.Number({ minimum: 0, maximum: 1 })),
          notes: Type.Optional(Type.String()),
          sourceIds: Type.Optional(Type.Array(Type.String({ minLength: 1 }))),
          lastVerifiedAt: Type.Optional(Type.String()),
        },
        { additionalProperties: false },
      ),
      async execute(params, config, context) {
        context.signal?.throwIfAborted();
        const claim = await storeFor(config.dataDir).captureKnowledgeClaim(params);
        return { claim: compact(claim) };
      },
    }),
    tool({
      name: "kairo_knowledge_get",
      label: "Get KAIRO Knowledge",
      description: "Read one durable knowledge claim, including epistemic/provenance metadata and its Markdown body.",
      parameters: Type.Object(
        {
          project: Type.String({ minLength: 1 }),
          claimId: Type.String({ minLength: 1 }),
        },
        { additionalProperties: false },
      ),
      async execute({ project, claimId }, config, context) {
        context.signal?.throwIfAborted();
        return { claim: await storeFor(config.dataDir).getKnowledgeClaim(project, claimId) };
      },
    }),
    tool({
      name: "kairo_background_schedule",
      label: "Schedule KAIRO Background Work",
      description:
        "Schedule one bounded future KAIRO agent turn in the current session. V0 is limited to A0-A2 internal/research work and never grants publishing, financial, destructive, or other A3+ external authority.",
      parameters: backgroundScheduleParameters,
      factory({ api, config, toolContext }) {
        const sessionKey = toolContext.sessionKey;
        if (!sessionKey) return null;
        return {
          name: "kairo_background_schedule",
          label: "Schedule KAIRO Background Work",
          description:
            "Schedule one bounded future KAIRO agent turn in the current session. V0 is limited to A0-A2 internal/research work.",
          parameters: backgroundScheduleParameters,
          async execute(_toolCallId, rawParams, signal) {
            signal?.throwIfAborted();
            const params = rawParams as {
              project: string;
              title: string;
              instructions: string;
              at: string;
              authorityCeiling?: "A0" | "A1" | "A2";
              announce?: boolean;
            };
            const store = storeFor(config.dataDir);
            const project = await store.getProject(params.project);
            const at = parseAbsoluteSchedule(params.at);
            const authorityCeiling = params.authorityCeiling ?? "A2";
            const tag = `kairo-bg-${project.slug}-${randomUUID().slice(0, 8)}`;
            const handle = await api.session.workflow.scheduleSessionTurn({
              sessionKey,
              agentId: toolContext.agentId,
              at,
              deleteAfterRun: true,
              deliveryMode: params.announce === false ? "none" : "announce",
              name: `KAIRO: ${params.title}`,
              tag,
              message: backgroundPrompt({
                project: project.slug,
                title: params.title,
                instructions: params.instructions,
                authorityCeiling,
              }),
            });
            if (!handle) throw new Error("OpenClaw did not return a scheduler handle for KAIRO background work.");
            return {
              schedule: {
                id: handle.id,
                tag,
                project: project.slug,
                at: at.toISOString(),
                authority_ceiling: authorityCeiling,
                delivery_mode: params.announce === false ? "none" : "announce",
              },
              limitation:
                "V0 scheduling uses OpenClaw Cron, but KAIRO task/job persistence and hard model-cost ceilings are not implemented yet.",
            };
          },
        };
      },
    }),
  ],
});
