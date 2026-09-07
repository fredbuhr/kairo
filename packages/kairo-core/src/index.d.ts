export type ProjectStatus = "inbox" | "incubation" | "active" | "waiting" | "paused" | "completed" | "archived";
export type IdeaStatus = "captured" | "exploring" | "incubation" | "promoted" | "rejected";
export type TaskStatus = "todo" | "queued" | "running" | "blocked" | "waiting_user" | "waiting_external" | "completed" | "abandoned" | "failed";
export type JobStatus = "scheduling" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type JobStepStatus = "started" | "completed";
export type JobStepDisposition = "started" | "already_started" | "completed" | "already_completed";
export type EpistemicStatus = "fact" | "hypothesis" | "deduction" | "opinion" | "unknown";
export type AuthorityLevel = "A0" | "A1" | "A2" | "A3" | "A4" | "A5";
export type SourceKind = "url" | "document" | "dataset" | "conversation" | "note" | "other";

export interface KairoRecord {
  id: string;
  type: string;
  created_at?: string;
  updated_at?: string;
  body?: string;
  [key: string]: unknown;
}

export interface ProjectRecord extends KairoRecord {
  type: "project";
  slug: string;
  name: string;
  status: ProjectStatus;
  summary: string;
}

export interface IdeaRecord extends KairoRecord {
  type: "idea";
  project_id: string;
  project_slug: string;
  title: string;
  status: IdeaStatus;
}

export interface DecisionRecord extends KairoRecord {
  type: "decision";
  project_id: string;
  project_slug: string;
  title: string;
}

export interface TaskRecord extends KairoRecord {
  type: "task";
  project_id: string;
  project_slug: string;
  title: string;
  owner: string;
  status: TaskStatus;
  authority_ceiling: AuthorityLevel;
}

export interface JobStepRecord {
  key: string;
  status: JobStepStatus;
  started_at: string;
  description?: string;
  completed_at?: string;
  summary?: string;
}

export interface JobRecord extends KairoRecord {
  type: "job";
  project_id: string;
  project_slug: string;
  title: string;
  status: JobStatus;
  authority_ceiling: AuthorityLevel;
  scheduled_for?: string;
  requested_budget?: number;
  budget_enforced?: boolean;
  scheduler_id?: string;
  scheduler_tag?: string;
  scheduler_kind?: string;
  execution_steps?: JobStepRecord[];
  completion_summary?: string;
  failure_reason?: string;
}

export interface JobStepResult {
  job: JobRecord;
  step: JobStepRecord;
  disposition: JobStepDisposition;
}

export interface JobUsageCounters {
  input?: number;
  output?: number;
  cacheRead?: number;
  cacheWrite?: number;
  total?: number;
}

export interface JobUsageSummary {
  runs: number;
  model_calls: number;
  tool_calls: number;
  provider_models: string[];
  usage: JobUsageCounters;
  known_cost_usd: number;
  priced_runs: number;
  unpriced_runs: number;
  cost_complete: boolean;
}

export interface JobUsageState {
  type: "job_usage";
  job_id: string;
  project_slug: string;
  scheduler_id?: string;
  created_at: string;
  updated_at: string;
  runs: unknown[];
}

export interface KnowledgeClaimRecord extends KairoRecord {
  type: "knowledge_claim";
  project_id: string;
  project_slug: string;
  title: string;
  epistemic_status: EpistemicStatus;
}

export interface SourceRecord extends KairoRecord {
  type: "source";
  project_id: string;
  project_slug: string;
  title: string;
  kind: SourceKind;
  locator: string;
}

export class KairoError extends Error {
  code: string;
  constructor(code: string, message: string);
}

export function createId(prefix: string): string;
export function slugify(value: string): string;
export function parseMarkdown(content: string): { metadata: Record<string, unknown>; body: string };
export function serializeMarkdown(metadata: Record<string, unknown>, body: string): string;

export class KairoStore {
  constructor(options: { dataDir: string; clock?: () => Date });
  readonly projectsDir: string;
  init(): Promise<void>;

  createProject(input: {
    name: string;
    slug?: string;
    summary?: string;
    status?: ProjectStatus;
    parent?: string;
  }): Promise<ProjectRecord>;
  getProject(ref: string): Promise<ProjectRecord>;
  listProjects(): Promise<ProjectRecord[]>;

  captureIdea(input: {
    project: string;
    title: string;
    content: string;
    rationale?: string;
    status?: IdeaStatus;
    epistemicStatus?: EpistemicStatus;
    sourceKind?: string;
    sourceSession?: string;
    originalText?: string;
  }): Promise<IdeaRecord>;
  getIdea(project: string, ideaId: string): Promise<IdeaRecord>;
  listIdeas(project: string): Promise<IdeaRecord[]>;

  recordDecision(input: {
    project: string;
    title: string;
    statement: string;
    rationale?: string;
    alternatives?: string[];
    consequences?: string;
    confidence?: number;
    sourceIds?: string[];
    supersedes?: string;
  }): Promise<DecisionRecord>;
  getDecision(project: string, decisionId: string): Promise<DecisionRecord>;

  createTask(input: {
    project: string;
    title: string;
    description?: string;
    owner?: string;
    status?: TaskStatus;
    authorityCeiling?: AuthorityLevel;
    deadline?: string;
    budget?: number;
    dependencies?: string[];
  }): Promise<TaskRecord>;
  getTask(project: string, taskId: string): Promise<TaskRecord>;

  captureKnowledgeClaim(input: {
    project: string;
    title: string;
    claim: string;
    epistemicStatus: EpistemicStatus;
    confidence?: number;
    notes?: string;
    sourceIds?: string[];
    lastVerifiedAt?: string;
  }): Promise<KnowledgeClaimRecord>;
  getKnowledgeClaim(project: string, claimId: string): Promise<KnowledgeClaimRecord>;

  captureSource(input: {
    project: string;
    title: string;
    kind: SourceKind;
    locator: string;
    summary?: string;
  }): Promise<SourceRecord>;
  getSource(project: string, sourceId: string): Promise<SourceRecord>;
}

export class KairoJobLedger {
  constructor(options: { dataDir: string; clock?: () => Date });

  createJob(input: {
    project: string;
    title: string;
    instructions: string;
    authorityCeiling?: AuthorityLevel;
    scheduledFor?: string;
    requestedBudget?: number;
    sourceSession?: string;
    taskId?: string;
  }): Promise<JobRecord>;

  linkScheduler(
    project: string,
    jobId: string,
    scheduler: { schedulerId: string; schedulerTag: string; schedulerKind?: string },
  ): Promise<JobRecord>;

  markRunning(project: string, jobId: string): Promise<JobRecord>;
  beginStep(
    project: string,
    jobId: string,
    input: { stepKey: string; description?: string },
  ): Promise<JobStepResult>;
  completeStep(
    project: string,
    jobId: string,
    input: { stepKey: string; summary: string },
  ): Promise<JobStepResult>;
  completeJob(project: string, jobId: string, input: { summary: string }): Promise<JobRecord>;
  failJob(project: string, jobId: string, input: { reason: string }): Promise<JobRecord>;
  cancelJob(project: string, jobId: string, input?: { reason?: string }): Promise<JobRecord>;
  getJob(project: string, jobId: string): Promise<JobRecord>;
  listJobs(project: string): Promise<JobRecord[]>;
}

export class KairoJobUsageLedger {
  constructor(options: { dataDir: string; clock?: () => Date });
  findJobBySchedulerId(schedulerId: string): Promise<{
    project_slug: string;
    job_id: string;
    scheduler_id: string;
  } | null>;
  recordLlmOutputBySchedulerId(schedulerId: string, input: Record<string, unknown>): Promise<unknown>;
  recordFinalSnapshotBySchedulerId(schedulerId: string, input: Record<string, unknown>): Promise<unknown>;
  recordToolCallBySchedulerId(schedulerId: string, input: Record<string, unknown>): Promise<unknown>;
  recordLlmOutput(project: string, jobId: string, input: Record<string, unknown>): Promise<unknown>;
  recordFinalSnapshot(project: string, jobId: string, input: Record<string, unknown>): Promise<unknown>;
  recordToolCall(project: string, jobId: string, input: Record<string, unknown>): Promise<unknown>;
  getUsage(project: string, jobId: string): Promise<{ state: JobUsageState; summary: JobUsageSummary }>;
}
