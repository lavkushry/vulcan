export type JobStatus =
  | "PENDING_APPROVAL" | "QUEUED" | "RUNNING" | "VERIFYING" | "SUCCESS"
  | "FAILED" | "REJECTED" | "TIMEOUT_DENIED";

export interface ParamSpec {
  name: string; type: "string" | "enum" | "integer"; required: boolean;
  description?: string; choices?: string[];
}

export interface CatalogSummary {
  identifier: string; name: string; engine: "ansible" | "terraform";
  risk_tier: "LOW" | "MEDIUM" | "HIGH"; description: string;
  requires_maker_checker: boolean; requires_chg: boolean; params: ParamSpec[];
}

export interface IntentResult {
  status: "READY" | "NEEDS_INPUT" | "REJECTED";
  match?: CatalogSummary;
  parameters: Record<string, unknown>;
  missing_fields: ParamSpec[];
  confidence?: number;
  reason?: string;
  suggestions?: { identifier: string; name: string }[];
  servicenow_chg?: string;
}

export interface Job {
  id: string; correlation_id: string; identifier: string; name: string;
  engine: string; risk_tier: string; requester_id: string; approver_id: string | null;
  parameters: Record<string, unknown>; status: JobStatus;
  servicenow_chg: string | null; created_at: string;
  approved_at: string | null; completed_at: string | null;
  exit_code: number | null; diagnostic: string | null;
}

export interface WsEvent {
  seq: number; type: "status" | "stdout" | "diagnostic";
  data: Record<string, any>; timestamp: string;
}

export const STATUS_STYLE: Record<string, string> = {
  PENDING_APPROVAL: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  QUEUED: "border-blue-500/40 bg-blue-500/10 text-blue-300",
  RUNNING: "border-cyan-500/40 bg-cyan-500/10 text-cyan-300",
  VERIFYING: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  SUCCESS: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  FAILED: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  REJECTED: "border-slate-600 bg-slate-700/20 text-slate-400",
  TIMEOUT_DENIED: "border-orange-500/40 bg-orange-500/10 text-orange-300",
};

export const FILTER_LABELS: Record<string, string> = {
  ALL: "All", PENDING_APPROVAL: "Pending", QUEUED: "Queued", RUNNING: "Running", VERIFYING: "Verifying",
  SUCCESS: "Success", FAILED: "Failed", REJECTED: "Rejected", TIMEOUT_DENIED: "Timeout",
};
