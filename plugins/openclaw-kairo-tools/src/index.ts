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

const configSchema = Type.Object(
  {
    dataDir: Type.String({
      minLength: 1,
      description: "Absolute path to KAIRO runtime-private domain data.",
    }),
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

export default defineToolPlugin({
  id: "kairo-tools",
  name: "KAIRO Tools",
  description: "Durable KAIRO project and idea tools backed by the user-owned KAIRO domain store.",
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
  ],
});
