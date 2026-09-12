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
  target_resource?: string; target_resource_id?: string;
  parameters: Record<string, unknown>; status: JobStatus;
  servicenow_chg: string | null; created_at: string;
  approval_requested_at?: string | null;
  approved_at: string | null; completed_at: string | null;
  exit_code: number | null; diagnostic: string | null;
  capabilities?: {
    can_approve: boolean;
    can_reject: boolean;
    disabled_reason?: string | null;
  };
}

export interface WsEvent {
  seq: number; type: "status" | "stdout" | "diagnostic" | "lock_heartbeat";
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

export interface RoleDefinition {
  role: string;
  name: string;
  permissions: string[];
  total_permissions: number;
  description: string;
}

export interface PolicyRule {
  policy_id: string;
  name: string;
  description: string;
  enforcement_level: 'MANDATORY_BLOCK' | 'APPROVAL_GATE' | 'AUDIT_FLAG';
  rego_definition: string;
  is_active: boolean;
  tags: string[];
}

export interface PolicyEvaluationResult {
  decision: 'ALLOW' | 'REQUIRE_APPROVAL' | 'DENY';
  user_id: string;
  user_role: string;
  action_identifier: string;
  environment: string;
  passed_policies: string[];
  gated_policies: string[];
  denied_policies: string[];
  reasons: string[];
  evaluated_at: string;
}

export interface PolicySimulationRequest {
  user_id: string;
  action_identifier: string;
  environment: string;
  parameters?: Record<string, any>;
  risk_tier?: string;
  servicenow_chg?: string | null;
  is_freeze_active?: boolean;
  is_emergency?: boolean;
  approver_id?: string | null;
}

export interface CandidateProvenance {
  source_registry: 'terraform_registry' | 'ansible_galaxy' | string;
  upstream_url: string;
  upstream_repo: string;
  version: string;
  downloads: number;
  license: string;
  license_compliant: boolean;
  security_scan_status: string;
  suggested_defaults?: Record<string, any>;
  authors?: string[];
}

export interface CandidateItem {
  id: string;
  identifier: string;
  name: string;
  engine: 'ansible' | 'terraform' | string;
  category: string;
  risk_tier: string;
  curation_status: 'CANDIDATE' | 'DRAFTED_PR' | 'CURATED' | 'REJECTED';
  description: string;
  tags: string[];
  provenance: CandidateProvenance;
  input_schema?: Record<string, any>;
}

export interface CrawlResult {
  status: string;
  crawled_count: number;
  candidates: Array<{
    identifier: string;
    name: string;
    engine: string;
    license: string;
    license_compliant: boolean;
  }>;
}

export interface DraftPRResult {
  status: string;
  identifier: string;
  target_internal_repo: string;
  branch: string;
  pr_title: string;
  tarball_sha256: string;
  security_checklist: Record<string, string>;
  curation_status: string;
}

export interface ApproveCandidateResult {
  status: string;
  identifier: string;
  curation_status: string;
  internal_git_repo: string;
  internal_commit_sha: string;
  approver_id: string;
  promoted_catalog_item: {
    identifier: string;
    name: string;
    engine: string;
    risk_tier: string;
  };
}

export interface MerkleAuditRecord {
  id: number;
  correlation_id: string;
  timestamp: string;
  actor: string;
  action: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  current_hash: string;
}

export interface JobAuditVerification {
  correlation_id: string;
  job_id: string;
  job_name: string;
  job_status: string;
  chain_valid: boolean;
  verified_at: string;
  records_count: number;
  tip_hash: string;
  records: MerkleAuditRecord[];
}

// Distributed Conversational Chat Subsystem (CHAT-03)
export interface ChatTurnItem {
  turn_id: string;
  session_id: string;
  turn_index: number;
  role: "user" | "assistant" | "system";
  content: string;
  intent_state?: string | null;
  catalog_identifier?: string | null;
  parameters?: Record<string, any>;
  token_usage?: number | null;
  latency_ms?: number | null;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface ChatSessionSummary {
  session_id: string;
  user_id: string;
  title: string;
  turn_count: number;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  turns: ChatTurnItem[];
}

export interface AppendTurnResponse {
  session_id: string;
  user_turn: Record<string, any>;
  assistant_turn: Record<string, any>;
  intent_status: string;
  catalog_identifier?: string | null;
  catalog_item?: Record<string, any> | null;
  parameters: Record<string, any>;
  missing_fields: string[];
  refusal_reason?: string | null;
  tokens_used?: number | null;
  latency_ms?: number | null;
  disambiguation?: {
    deltaSim: number;
    candidates: any[];
  } | null;
}

// Topology-Aware Blast Radius & Affected Node Graph (UI-14)
export interface DownstreamDependency {
  service: string;
  role: string;
  health: 'HEALTHY' | 'WARN' | 'DEGRADED';
  traffic_rate: string;
  tier: 'TIER-1' | 'TIER-2' | 'TIER-3';
  failover_ready: boolean;
}

export interface PrimaryNodeInfo {
  hostname: string;
  ip_address: string;
  role: string;
  cluster: string;
  datacenter: string;
  redundancy_pair: string;
  failover_state: string;
}

export interface RollbackGuarantee {
  registered: boolean;
  verification_status: 'VERIFIED' | 'MANUAL_REQUIRED';
  playbook_identifier: string;
  target_resource: string;
  rto_estimate_seconds: number;
  evidence: string;
}

export interface BlastRadiusData {
  correlation_id: string;
  job_id: string;
  job_name: string;
  playbook_identifier: string;
  environment: 'PROD' | 'UAT' | 'DEV';
  target_resource: string;
  primary_node: PrimaryNodeInfo;
  downstream_dependencies: DownstreamDependency[];
  total_active_traffic: string;
  ingress_bandwidth: string;
  collateral_risk_tier: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  requires_maker_checker: boolean;
  servicenow_chg?: string | null;
  rollback_guarantee: RollbackGuarantee;
  evaluated_at: string;
}

// Dual-Mode Monaco HCL/YAML Code Diff Inspector (UI-23)
export interface DeclarativeCodeDiff {
  correlation_id: string;
  job_id: string;
  playbook_identifier: string;
  engine: 'ansible' | 'terraform' | string;
  file_path: string;
  git_head_sha: string;
  git_branch: string;
  synthesized_revision: string;
  parameters: Record<string, any>;
  base_code: string;
  synthesized_code: string;
  diff_unified: string;
  generated_at: string;
}

// Multi-Cluster Topology Radar (UI-25)
export interface ClusterNodeSummary {
  id: string;
  name: string;
  region: string;
  status: 'HEALTHY' | 'DEGRADED' | 'STANDBY';
  role: 'PRIMARY_LEADER' | 'ACTIVE_REPLICA' | 'DISASTER_RECOVERY';
  nodes_count: number;
  active_runners: number;
  runner_capacity: number;
  latency_p95_ms: number;
  redlock_quorum_node: string;
  quorum_healthy: boolean;
  datacenter_location: string;
}

export interface ClusterTopology {
  clusters: ClusterNodeSummary[];
  global_consensus: {
    quorum_protocol: string;
    active_nodes: number;
    total_nodes: number;
    status: string;
    fencing_epoch: number;
    watchdog_health: string;
  };
  cross_region_replication: {
    mode: string;
    rpo_measured_seconds: number;
    rto_measured_seconds: number;
    last_heartbeat: string;
  };
  queried_at: string;
}

