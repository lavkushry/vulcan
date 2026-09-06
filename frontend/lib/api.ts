import type { IntentResult, Job } from "./types";
import { getApiBaseUrl } from "./env";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail: any = null;
    try { detail = (await res.json())?.detail; } catch { /* ignore */ }
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail?.errors) ? detail.errors.join("; ")
      : detail?.message ?? `Request failed (${res.status})`;
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  resolveIntent: (text: string) => req<IntentResult>("POST", "/api/v1/intent/resolve", { text }),
  createJob: async (p: { identifier: string; parameters: Record<string, unknown>; requester_id: string; servicenow_chg?: string | null }) => {
    const job = await req<Job>("POST", "/api/v1/jobs", p);
    if (job.status === "QUEUED") {
      try { await req("POST", `/api/v1/jobs/${job.correlation_id ?? job.id}/execute`); } catch { /* ignore */ }
    }
    return job;
  },
  listJobs: (currentUser?: string) => req<Job[]>("GET", `/api/v1/jobs${currentUser ? `?current_user=${encodeURIComponent(currentUser)}` : ""}`).then((r) => Array.isArray(r) ? r : (r as any).jobs),
  approveJob: async (id: string, approver_id: string) => {
    const job = await req<Job>("POST", `/api/v1/jobs/${id}/approve`, { approver_id });
    try { await req("POST", `/api/v1/jobs/${job.correlation_id ?? job.id}/execute`); } catch { /* ignore */ }
    return job;
  },
  rejectJob: (id: string, approver_id: string) => req<Job>("POST", `/api/v1/jobs/${id}/reject`, { approver_id }),
  listRoles: () => req<import("./types").RoleDefinition[]>("GET", "/api/v1/roles"),
  listPolicies: () => req<import("./types").PolicyRule[]>("GET", "/api/v1/policies"),
  togglePolicy: (id: string) => req<{ ok: boolean; message: string }>("POST", `/api/v1/policies/${id}/toggle`),
  evaluatePolicy: (p: import("./types").PolicySimulationRequest) => req<import("./types").PolicyEvaluationResult>("POST", "/api/v1/policies/evaluate", p),
  // Curation Gate Endpoints (REG-01 / REG-02)
  listCandidates: (filters?: { source?: string; status?: string; search?: string }) => {
    const params = new URLSearchParams();
    if (filters?.source) params.append("source", filters.source);
    if (filters?.status) params.append("status", filters.status);
    if (filters?.search) params.append("search", filters.search);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return req<import("./types").CandidateItem[]>("GET", `/api/v1/curation/candidates${qs}`);
  },
  crawlCandidates: (tf_count = 10, galaxy_count = 10) =>
    req<import("./types").CrawlResult>("POST", "/api/v1/curation/crawl", { tf_count, galaxy_count }),
  draftCandidatePR: (id: string, target_internal_repo = "git@github.internal.bank.com:automation/catalog-modules.git") =>
    req<import("./types").DraftPRResult>("POST", `/api/v1/curation/candidates/${encodeURIComponent(id)}/draft-pr`, { target_internal_repo }),
  approveCandidate: (id: string, approver_id: string, internal_git_repo: string, internal_commit_sha: string) =>
    req<import("./types").ApproveCandidateResult>("POST", `/api/v1/curation/candidates/${encodeURIComponent(id)}/approve`, {
      approver_id,
      internal_git_repo,
      internal_commit_sha,
    }),
  rejectCandidate: (id: string, reviewer_id: string, reason: string) =>
    req<{ status: string; identifier: string; curation_status: string; reason: string }>(
      "POST",
      `/api/v1/curation/candidates/${encodeURIComponent(id)}/reject`,
      { reviewer_id, reason }
    ),
};

// Enterprise Banking Personas & RBAC Mapping
export const DEMO_USERS = [
  { id: "eng.alice", label: "Alice Cooper", role: "OPERATOR", roleBadge: "Operator", desc: "Requesting Engineer" },
  { id: "lead.bob", label: "Bob Martin", role: "APPROVING_LEAD", roleBadge: "Approving Lead", desc: "Lead SRE / Approver" },
  { id: "sec.carol", label: "Carol Danvers", role: "SECURITY_ADMIN", roleBadge: "Security Admin", desc: "InfoSec & Compliance" },
  { id: "admin.dave", label: "Dave Bowman", role: "PLATFORM_ADMIN", roleBadge: "Platform Admin", desc: "Platform Architect" },
  { id: "audit.emma", label: "Emma Watson", role: "AUDITOR", roleBadge: "Auditor", desc: "Regulatory SOX Auditor" },
];

