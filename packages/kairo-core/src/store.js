import { mkdir, readFile, readdir, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { createId, assertSafeId, slugify } from "./ids.js";
import { parseMarkdown, serializeMarkdown } from "./frontmatter.js";
import { KairoError } from "./errors.js";

const PROJECT_STATUSES = new Set(["inbox", "incubation", "active", "waiting", "paused", "completed", "archived"]);
const IDEA_STATUSES = new Set(["captured", "exploring", "incubation", "promoted", "rejected"]);
const TASK_STATUSES = new Set(["todo", "queued", "running", "blocked", "waiting_user", "waiting_external", "completed", "abandoned", "failed"]);
const EPISTEMIC_STATUSES = new Set(["fact", "hypothesis", "deduction", "opinion", "unknown"]);
const AUTHORITY_LEVELS = new Set(["A0", "A1", "A2", "A3", "A4", "A5"]);
const SOURCE_KINDS = new Set(["url", "document", "dataset", "conversation", "note", "other"]);

function nowIso(clock) {
  return clock().toISOString();
}

function requireText(value, label) {
  const text = String(value ?? "").trim();
  if (!text) throw new TypeError(`${label} is required.`);
  return text;
}

function optionalText(value) {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function optionalStringArray(value, label) {
  if (value === undefined || value === null) return undefined;
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.trim())) {
    throw new TypeError(`${label} must be an array of non-empty strings.`);
  }
  return value.map((item) => item.trim());
}

function optionalConfidence(value) {
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0 || number > 1) {
    throw new TypeError("confidence must be a number between 0 and 1.");
  }
  return number;
}

async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function atomicWrite(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const temp = `${filePath}.tmp-${process.pid}-${Math.random().toString(16).slice(2)}`;
  await writeFile(temp, content, { encoding: "utf8", flag: "wx" });
  await rename(temp, filePath);
}

function projectBody({ name, summary }) {
  return `# ${name}\n\n## Summary\n${summary || "No summary yet."}`;
}

function ideaBody({ title, content, rationale, originalText }) {
  const sections = [`# ${title}`, `## Idea\n${content}`];
  if (rationale) sections.push(`## Rationale\n${rationale}`);
  if (originalText) sections.push(`## Original wording\n> ${originalText.replace(/\n/g, "\n> ")}`);
  return sections.join("\n\n");
}

function decisionBody({ title, statement, rationale, alternatives, consequences }) {
  const sections = [`# ${title}`, `## Decision\n${statement}`];
  if (rationale) sections.push(`## Rationale\n${rationale}`);
  if (alternatives?.length) sections.push(`## Alternatives considered\n${alternatives.map((item) => `- ${item}`).join("\n")}`);
  if (consequences) sections.push(`## Consequences\n${consequences}`);
  return sections.join("\n\n");
}

function taskBody({ title, description }) {
  return `# ${title}\n\n## Task\n${description || "No description yet."}`;
}

function claimBody({ title, claim, notes }) {
  const sections = [`# ${title}`, `## Claim\n${claim}`];
  if (notes) sections.push(`## Notes\n${notes}`);
  return sections.join("\n\n");
}

function sourceBody({ title, locator, summary }) {
  const sections = [`# ${title}`, `## Locator\n${locator}`];
  if (summary) sections.push(`## Summary\n${summary}`);
  return sections.join("\n\n");
}

export class KairoStore {
  constructor({ dataDir, clock = () => new Date() }) {
    this.dataDir = path.resolve(requireText(dataDir, "dataDir"));
    this.clock = clock;
  }

  get projectsDir() {
    return path.join(this.dataDir, "projects");
  }

  async init() {
    await mkdir(this.projectsDir, { recursive: true });
  }

  async createProject({ name, slug, summary = "", status = "active", parent }) {
    await this.init();
    const normalizedName = requireText(name, "Project name");
    const normalizedSlug = slugify(slug || normalizedName);
    if (!PROJECT_STATUSES.has(status)) throw new TypeError(`Invalid project status: ${status}`);

    const dir = path.join(this.projectsDir, normalizedSlug);
    const file = path.join(dir, "project.md");
    if (await exists(file)) {
      throw new KairoError("PROJECT_EXISTS", `Project '${normalizedSlug}' already exists.`);
    }

    const timestamp = nowIso(this.clock);
    const project = {
      id: createId("project"),
      type: "project",
      slug: normalizedSlug,
      name: normalizedName,
      status,
      summary: String(summary ?? "").trim(),
      created_at: timestamp,
      updated_at: timestamp,
    };

    if (parent) {
      const parentRecord = await this.getProject(parent);
      project.parent_id = parentRecord.id;
      project.parent_slug = parentRecord.slug;
    }

    await atomicWrite(file, serializeMarkdown(project, projectBody(project)));
    return project;
  }

  async getProject(ref) {
    await this.init();
    const slug = slugify(ref);
    const file = path.join(this.projectsDir, slug, "project.md");
    if (!(await exists(file))) {
      throw new KairoError("PROJECT_NOT_FOUND", `Project '${slug}' was not found.`);
    }
    const { metadata, body } = parseMarkdown(await readFile(file, "utf8"));
    return { ...metadata, body };
  }

  async listProjects() {
    await this.init();
    const entries = await readdir(this.projectsDir, { withFileTypes: true });
    const projects = [];
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      try {
        projects.push(await this.getProject(entry.name));
      } catch (error) {
        if (error instanceof KairoError && error.code === "PROJECT_NOT_FOUND") continue;
        throw error;
      }
    }
    return projects.sort((a, b) => String(a.name).localeCompare(String(b.name)));
  }

  async captureIdea({ project, title, content, rationale, status = "captured", epistemicStatus, sourceKind = "conversation", sourceSession, originalText }) {
    const projectRecord = await this.getProject(project);
    const normalizedTitle = requireText(title, "Idea title");
    const normalizedContent = requireText(content, "Idea content");
    if (!IDEA_STATUSES.has(status)) throw new TypeError(`Invalid idea status: ${status}`);
    if (epistemicStatus && !EPISTEMIC_STATUSES.has(epistemicStatus)) {
      throw new TypeError(`Invalid epistemic status: ${epistemicStatus}`);
    }

    const timestamp = nowIso(this.clock);
    const idea = {
      id: createId("idea"),
      type: "idea",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      status,
      created_at: timestamp,
      updated_at: timestamp,
      provenance_kind: requireText(sourceKind, "sourceKind"),
    };
    if (epistemicStatus) idea.epistemic_status = epistemicStatus;
    const normalizedSession = optionalText(sourceSession);
    if (normalizedSession) idea.provenance_session = normalizedSession;

    const file = path.join(this.projectsDir, projectRecord.slug, "ideas", `${idea.id}.md`);
    await atomicWrite(file, serializeMarkdown(idea, ideaBody({
      title: normalizedTitle,
      content: normalizedContent,
      rationale: optionalText(rationale),
      originalText: optionalText(originalText),
    })));

    return { ...idea, content: normalizedContent, rationale: optionalText(rationale), original_text: optionalText(originalText) };
  }

  async getIdea(project, ideaId) {
    return this.#getProjectEntity(project, "ideas", ideaId, "idea", "IDEA_NOT_FOUND");
  }

  async listIdeas(project) {
    return this.#listProjectEntities(project, "ideas", "idea", "IDEA_NOT_FOUND");
  }

  async recordDecision({ project, title, statement, rationale, alternatives, consequences, confidence, sourceIds, supersedes }) {
    const projectRecord = await this.getProject(project);
    const normalizedTitle = requireText(title, "Decision title");
    const normalizedStatement = requireText(statement, "Decision statement");
    const timestamp = nowIso(this.clock);
    const decision = {
      id: createId("decision"),
      type: "decision",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      created_at: timestamp,
      updated_at: timestamp,
    };
    const normalizedConfidence = optionalConfidence(confidence);
    if (normalizedConfidence !== undefined) decision.confidence = normalizedConfidence;
    const normalizedSources = optionalStringArray(sourceIds, "sourceIds");
    if (normalizedSources?.length) decision.source_ids = normalizedSources;
    if (supersedes) decision.supersedes = assertSafeId(requireText(supersedes, "supersedes"), "supersedes");

    const file = path.join(this.projectsDir, projectRecord.slug, "decisions", `${decision.id}.md`);
    await atomicWrite(file, serializeMarkdown(decision, decisionBody({
      title: normalizedTitle,
      statement: normalizedStatement,
      rationale: optionalText(rationale),
      alternatives: optionalStringArray(alternatives, "alternatives"),
      consequences: optionalText(consequences),
    })));
    return decision;
  }

  async getDecision(project, decisionId) {
    return this.#getProjectEntity(project, "decisions", decisionId, "decision", "DECISION_NOT_FOUND");
  }

  async createTask({ project, title, description, owner = "user", status = "todo", authorityCeiling = "A1", deadline, budget, dependencies }) {
    const projectRecord = await this.getProject(project);
    const normalizedTitle = requireText(title, "Task title");
    if (!TASK_STATUSES.has(status)) throw new TypeError(`Invalid task status: ${status}`);
    if (!AUTHORITY_LEVELS.has(authorityCeiling)) throw new TypeError(`Invalid authority ceiling: ${authorityCeiling}`);
    const normalizedOwner = requireText(owner, "Task owner");
    if (!(normalizedOwner === "user" || normalizedOwner === "kairo" || normalizedOwner.startsWith("agent:"))) {
      throw new TypeError("Task owner must be user, kairo, or agent:<id>.");
    }
    if (budget !== undefined && (!Number.isFinite(Number(budget)) || Number(budget) < 0)) {
      throw new TypeError("budget must be a non-negative number.");
    }

    const timestamp = nowIso(this.clock);
    const task = {
      id: createId("task"),
      type: "task",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      owner: normalizedOwner,
      status,
      authority_ceiling: authorityCeiling,
      created_at: timestamp,
      updated_at: timestamp,
    };
    const normalizedDeadline = optionalText(deadline);
    if (normalizedDeadline) task.deadline = normalizedDeadline;
    if (budget !== undefined) task.budget = Number(budget);
    const normalizedDependencies = optionalStringArray(dependencies, "dependencies");
    if (normalizedDependencies?.length) task.dependencies = normalizedDependencies;

    const file = path.join(this.projectsDir, projectRecord.slug, "tasks", `${task.id}.md`);
    await atomicWrite(file, serializeMarkdown(task, taskBody({ title: normalizedTitle, description: optionalText(description) })));
    return task;
  }

  async getTask(project, taskId) {
    return this.#getProjectEntity(project, "tasks", taskId, "task", "TASK_NOT_FOUND");
  }

  async captureKnowledgeClaim({ project, title, claim, epistemicStatus, confidence, notes, sourceIds, lastVerifiedAt }) {
    const projectRecord = await this.getProject(project);
    const normalizedTitle = requireText(title, "Knowledge title");
    const normalizedClaim = requireText(claim, "Knowledge claim");
    if (!EPISTEMIC_STATUSES.has(epistemicStatus)) {
      throw new TypeError(`Invalid epistemic status: ${epistemicStatus}`);
    }

    const timestamp = nowIso(this.clock);
    const record = {
      id: createId("claim"),
      type: "knowledge_claim",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      epistemic_status: epistemicStatus,
      created_at: timestamp,
      updated_at: timestamp,
    };
    const normalizedConfidence = optionalConfidence(confidence);
    if (normalizedConfidence !== undefined) record.confidence = normalizedConfidence;
    const normalizedSources = optionalStringArray(sourceIds, "sourceIds");
    if (normalizedSources?.length) record.source_ids = normalizedSources;
    const verified = optionalText(lastVerifiedAt);
    if (verified) record.last_verified_at = verified;

    const file = path.join(this.projectsDir, projectRecord.slug, "knowledge", `${record.id}.md`);
    await atomicWrite(file, serializeMarkdown(record, claimBody({
      title: normalizedTitle,
      claim: normalizedClaim,
      notes: optionalText(notes),
    })));
    return record;
  }

  async getKnowledgeClaim(project, claimId) {
    return this.#getProjectEntity(project, "knowledge", claimId, "claim", "CLAIM_NOT_FOUND");
  }

  async captureSource({ project, title, kind, locator, summary }) {
    const projectRecord = await this.getProject(project);
    const normalizedTitle = requireText(title, "Source title");
    if (!SOURCE_KINDS.has(kind)) throw new TypeError(`Invalid source kind: ${kind}`);
    const normalizedLocator = requireText(locator, "Source locator");
    const timestamp = nowIso(this.clock);
    const source = {
      id: createId("source"),
      type: "source",
      project_id: projectRecord.id,
      project_slug: projectRecord.slug,
      title: normalizedTitle,
      kind,
      locator: normalizedLocator,
      created_at: timestamp,
      updated_at: timestamp,
    };
    const file = path.join(this.projectsDir, projectRecord.slug, "sources", `${source.id}.md`);
    await atomicWrite(file, serializeMarkdown(source, sourceBody({
      title: normalizedTitle,
      locator: normalizedLocator,
      summary: optionalText(summary),
    })));
    return source;
  }

  async getSource(project, sourceId) {
    return this.#getProjectEntity(project, "sources", sourceId, "source", "SOURCE_NOT_FOUND");
  }

  async #getProjectEntity(project, directory, entityId, prefix, notFoundCode) {
    const projectRecord = await this.getProject(project);
    const safeId = assertSafeId(requireText(entityId, `${prefix}Id`), `${prefix}Id`);
    if (!safeId.startsWith(`${prefix}_`)) throw new TypeError(`Invalid ${prefix}Id.`);
    const file = path.join(this.projectsDir, projectRecord.slug, directory, `${safeId}.md`);
    if (!(await exists(file))) {
      throw new KairoError(notFoundCode, `${prefix} '${safeId}' was not found in '${projectRecord.slug}'.`);
    }
    const { metadata, body } = parseMarkdown(await readFile(file, "utf8"));
    return { ...metadata, body };
  }

  async #listProjectEntities(project, directory, prefix, notFoundCode) {
    const projectRecord = await this.getProject(project);
    const dir = path.join(this.projectsDir, projectRecord.slug, directory);
    if (!(await exists(dir))) return [];
    const entries = await readdir(dir, { withFileTypes: true });
    const items = [];
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
      const id = entry.name.slice(0, -3);
      try {
        items.push(await this.#getProjectEntity(projectRecord.slug, directory, id, prefix, notFoundCode));
      } catch (error) {
        if (error instanceof KairoError && error.code === notFoundCode) continue;
        throw error;
      }
    }
    return items.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  }
}
