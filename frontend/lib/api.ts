import type { IntentResult, Job } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
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
  listJobs: () => req<{ jobs: Job[] } | Job[]>("GET", "/api/v1/jobs").then((r) => Array.isArray(r) ? r : r.jobs),
  approveJob: async (id: string, approver_id: string) => {
    const job = await req<Job>("POST", `/api/v1/jobs/${id}/approve`, { approver_id });
    try { await req("POST", `/api/v1/jobs/${job.correlation_id ?? job.id}/execute`); } catch { /* ignore */ }
    return job;
  },
  rejectJob: (id: string, approver_id: string) => req<Job>("POST", `/api/v1/jobs/${id}/reject`, { approver_id }),
};

// Phase 4: replace with real SAML/OIDC identity.
export const DEMO_USERS = [
  { id: "eng.alice", label: "Alice · Requesting Engineer" },
  { id: "lead.bob", label: "Bob · Approving Lead" },
];
