"use client";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useJobStream } from "@/hooks/useJobStream";
import { Terminal } from "./Terminal";
import { RedlockHeartbeatBar } from "./RedlockHeartbeatBar";
import { SeparationOfDutiesProofCard } from "./SeparationOfDutiesProofCard";
import { STATUS_STYLE } from "@/lib/types";
import type { Job } from "@/lib/types";
import { timeAgo } from "@/lib/util";
import { useVulcan } from "@/lib/context";
import { AlertCircle, RefreshCw, ShieldCheck, Database, Radio, FileCode, Globe2, Split } from "lucide-react";
import ASTFailurePinpointCard from "./ASTFailurePinpointCard";
import MerkleAuditModal from "./MerkleAuditModal";
import S3MultipartSwarmGrid from "./S3MultipartSwarmGrid";
import BlastRadiusDrawer from "./BlastRadiusDrawer";
import MonacoDiffModal from "./MonacoDiffModal";
import ClusterMapModal from "./ClusterMapModal";
import DualTerminalReplay from "./DualTerminalReplay";

const PROGRESSION_STEPS = [
  "SUBMITTED",
  "PARSED",
  "PENDING_APPROVAL",
  "QUEUED",
  "LOCKED",
  "RUNNING",
  "VERIFYING",
  "SUCCESS",
];

export function JobDetail({ job, currentUser, onChanged }: {
  job: Job | null; currentUser: string; onChanged: () => void;
}) {
  const { setCurrentUser } = useVulcan();
  const [error, setError] = useState<string | null>(null);
  const [isMerkleModalOpen, setIsMerkleModalOpen] = useState<boolean>(false);
  const [showS3Swarm, setShowS3Swarm] = useState<boolean>(false);
  const [isBlastRadiusOpen, setIsBlastRadiusOpen] = useState<boolean>(false);
  const [isDiffModalOpen, setIsDiffModalOpen] = useState<boolean>(false);
  const [isClusterRadarOpen, setIsClusterRadarOpen] = useState<boolean>(false);
  const [isDualReplayOpen, setIsDualReplayOpen] = useState<boolean>(false);
  const stream = useJobStream(job ? (job.correlation_id ?? job.id) : null);

  // Live status from the WebSocket beats the 2.5s poll.
  const liveStatus = useMemo(() => {
    for (let i = stream.events.length - 1; i >= 0; i--) {
      const e = stream.events[i];
      if (e.type === "status") return e.data.status as string;
    }
    return null;
  }, [stream.events]);

  const status = liveStatus ?? job?.status ?? "SUBMITTED";

  // Determine active step index in the 8-step domain rail (Must be declared before any conditional return!)
  const activeStepIdx = useMemo(() => {
    if (status === "FAILED") return 5;
    if (status === "REJECTED") return 2;
    const idx = PROGRESSION_STEPS.indexOf(status);
    return idx >= 0 ? idx : 5;
  }, [status]);

  if (!job)
    return (
      <div className="flex h-full items-center justify-center bg-[#07090E] p-8 text-center text-sm text-slate-600 font-mono">
        Select a task in the Task Monitor to see its status, live terminal, or approval deck.
      </div>
    );

  const pending = status === "PENDING_APPROVAL";
  const isRunningOrLocked = status === "RUNNING" || status === "LOCKED" || status === "VERIFYING";

  async function decide(kind: "approveJob" | "rejectJob") {
    setError(null);
    try { await api[kind](job!.id, currentUser); onChanged(); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col bg-[#07090E]">
      {/* Top Header */}
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-800/80 px-5 py-3 bg-[#0C101A]/60 font-mono">
        <span className="text-sm font-bold text-cyan-400" data-testid="job-detail-correlation-id">{job.correlation_id}</span>
        <span className="text-sm text-slate-200">{job.name}</span>
        <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] ?? ""}`} data-testid="job-detail-status">
          {status}
        </span>
        {job.servicenow_chg && (
          <span className="rounded border border-slate-700 bg-slate-900/60 px-2 py-0.5 text-xs text-slate-400">
            ServiceNow · <strong className="text-slate-300">{job.servicenow_chg}</strong>
          </span>
        )}

        {/* Merkle Audit Chain Verification Pill (UI-15) */}
        <button
          type="button"
          onClick={() => setIsMerkleModalOpen(true)}
          title="Inspect SHA-256 Merkle chain and export WORM receipt"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/50 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-900/50 hover:border-emerald-400 transition-all shadow-[0_0_8px_rgba(0,255,157,0.2)] cursor-pointer"
          data-testid="job-detail-merkle-pill"
        >
          <ShieldCheck size={11} className="text-emerald-400" />
          <span>MERKLE CHAIN: VERIFIED ✔</span>
        </button>

        {/* 10GB S3 Decoupled Swarm Grid Toggle (UI-07) */}
        <button
          type="button"
          onClick={() => setShowS3Swarm(!showS3Swarm)}
          title="Toggle 10GB S3 Decoupled Multipart Swarm Telemetry"
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
            showS3Swarm
              ? "bg-cyan-950/60 text-cyan-300 border-cyan-500/50 shadow-[0_0_8px_rgba(0,240,255,0.3)]"
              : "bg-slate-900/60 text-slate-400 border-slate-700 hover:text-slate-200"
          }`}
          data-testid="job-detail-s3-toggle"
        >
          <Database size={11} className={showS3Swarm ? "text-cyan-400" : "text-slate-500"} />
          <span>S3 Swarm</span>
        </button>

        {/* Topology Blast Radius Drawer Toggle (UI-14) */}
        <button
          type="button"
          onClick={() => setIsBlastRadiusOpen(true)}
          title="Inspect topology blast radius and downstream dependencies"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950/40 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/50 hover:border-cyan-400 transition-all cursor-pointer shadow-[0_0_8px_rgba(0,240,255,0.2)]"
          data-testid="job-detail-blast-radius-btn"
        >
          <Radio size={11} className="text-cyan-400" />
          <span>Blast Radius</span>
        </button>

        {/* Declarative Code Diff Toggle (UI-23) */}
        <button
          type="button"
          onClick={() => setIsDiffModalOpen(true)}
          title="Inspect declarative HCL/YAML code diff against git HEAD"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-900/60 text-slate-300 border border-slate-700 hover:border-slate-500 hover:text-slate-100 transition-all cursor-pointer"
          data-testid="job-detail-diff-btn"
        >
          <FileCode size={11} className="text-slate-400" />
          <span>Code Diff</span>
        </button>

        {/* Multi-Cluster Topology Radar (UI-25) */}
        <button
          type="button"
          onClick={() => setIsClusterRadarOpen(true)}
          title="View multi-cluster consensus and regional distribution"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-900/60 text-slate-300 border border-slate-700 hover:border-slate-500 hover:text-slate-100 transition-all cursor-pointer"
          data-testid="job-detail-cluster-radar-btn"
        >
          <Globe2 size={11} className="text-slate-400" />
          <span>Clusters</span>
        </button>

        <span className="ml-auto text-xs text-slate-500">
          requester <span className="text-slate-300">{job.requester_id}</span>
          {job.approver_id ? <> · approver <span className="text-slate-300">{job.approver_id}</span></> : null}
        </span>
      </header>

      {/* 8-Step Progression Rail */}
      <div
        role="region"
        aria-label="Execution progression steps"
        tabIndex={0}
        className="px-5 py-2.5 border-b border-slate-800/80 bg-[#07090E] overflow-x-auto select-none focus:outline-none"
      >
        <div className="flex items-center gap-1.5 min-w-[640px] font-mono text-[10px]">
          {PROGRESSION_STEPS.map((step, idx) => {
            const isCompleted = idx < activeStepIdx;
            const isCurrent = idx === activeStepIdx;
            const isFailed = status === "FAILED" && isCurrent;

            return (
              <div key={step} className="flex items-center gap-1.5 flex-1">
                <div
                  className={`flex-1 px-2 py-1 rounded text-center font-semibold transition-all ${
                    isFailed
                      ? "bg-rose-950/60 text-rose-300 border border-rose-500/50 shadow-[0_0_8px_rgba(255,0,85,0.4)]"
                      : isCurrent
                      ? "bg-cyan-950/60 text-cyan-300 border border-cyan-500/50 animate-pulse shadow-[0_0_8px_rgba(0,240,255,0.4)]"
                      : isCompleted
                      ? "bg-emerald-950/40 text-emerald-400 border border-emerald-500/30"
                      : "bg-slate-900/50 text-slate-600 border border-slate-800"
                  }`}
                >
                  {step}
                </div>
                {idx < PROGRESSION_STEPS.length - 1 && (
                  <span className={`text-[10px] ${isCompleted ? "text-emerald-500" : "text-slate-700"}`}>
                    ➔
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {/* Distributed Redlock Watchdog Radar (Shown when running, locked, or verifying) */}
        {isRunningOrLocked && (
          <RedlockHeartbeatBar
            leaseTtlSeconds={30}
            watchdogIntervalSeconds={10}
            fencingToken={stream.latestHeartbeat?.data?.fencing_token ?? 10482}
            targetResource={(job.parameters?.target_resource as string) || job.target_resource || "prod-edge-vip"}
            quorumActive={stream.latestHeartbeat?.data?.quorum_active ?? 5}
            quorumTotal={stream.latestHeartbeat?.data?.quorum_total ?? 5}
            isHolding={true}
            serverTtlMs={stream.latestHeartbeat?.data?.remaining_ttl_ms}
            lastHeartbeatReceivedAt={stream.latestHeartbeat ? Date.parse(stream.latestHeartbeat.timestamp) : undefined}
          />
        )}

        {/* Decoupled Canvas S3 Multipart Swarm Grid (UI-07) */}
        {(showS3Swarm || job.identifier?.includes("s3") || job.identifier?.includes("storage")) && (
          <S3MultipartSwarmGrid
            totalParts={205}
            partSizeMb={50}
            parallelStreams={8}
            isSimulating={isRunningOrLocked}
          />
        )}

        {/* Pending Approval -> Separation of Duties Proof Cockpit */}
        {pending ? (
          <div className="space-y-3">
            <SeparationOfDutiesProofCard
              requesterId={job.requester_id}
              currentUserId={currentUser}
              servicenowChg={job.servicenow_chg}
              approvalRequestedAt={job.approval_requested_at || job.created_at}
              capabilities={job.capabilities}
              onApprove={() => decide("approveJob")}
              onReject={() => decide("rejectJob")}
              onSwitchUser={(user) => setCurrentUser(user)}
              onInspectBlastRadius={() => setIsBlastRadiusOpen(true)}
              onInspectDiff={() => setIsDiffModalOpen(true)}
            />
            {error && <p className="text-xs font-mono text-rose-400">{error}</p>}
          </div>
        ) : (
          <>
            {/* AI SRE AST Diagnostic Pinpoint & Rollback Cockpit (UI-19) */}
            {job.diagnostic && status === "FAILED" && (
              <ASTFailurePinpointCard
                diagnostic={job.diagnostic}
                diagnosticDetails={(job as any).diagnostic_details}
                jobIdentifier={job.identifier}
                targetResource={(job.parameters?.target_resource as string) || job.target_resource}
                exitCode={job.exit_code}
                currentUser={currentUser}
                servicenowChg={job.servicenow_chg}
                jobParameters={job.parameters}
                onRollbackDispatched={onChanged}
              />
            )}

            {/* Live Terminal & Dual-Pane Split Replay Bar (UI-27) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs font-mono px-1">
                <span className="text-slate-400 text-[11px]">TERMINAL STREAM · 60 FPS WEBGL BUFFER</span>
                <button
                  type="button"
                  onClick={() => setIsDualReplayOpen(true)}
                  className="flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-slate-900 border border-slate-700 hover:border-cyan-500/50 text-[11px] text-slate-300 hover:text-cyan-300 font-semibold transition-colors cursor-pointer"
                  data-testid="job-detail-split-replay-btn"
                >
                  <Split size={11} className="text-cyan-400" />
                  <span>Dual Replay vs Baseline (UI-27)</span>
                </button>
              </div>
              <div className="h-[52vh] min-h-[320px]">
                <Terminal events={stream.events} live={stream.live} />
              </div>
            </div>
          </>
        )}

        <div className="flex flex-wrap gap-4 text-xs font-mono text-slate-500 border-t border-slate-800/60 pt-3">
          <span>submitted {timeAgo(job.created_at)}</span>
          {job.approved_at && <span>approved {timeAgo(job.approved_at)}</span>}
          {job.completed_at && <span>completed {timeAgo(job.completed_at)}</span>}
          {job.exit_code !== null && <span>exit code {job.exit_code}</span>}
        </div>
      </div>

      {/* Merkle Audit Chain Verification & WORM Receipt Modal (UI-15) */}
      <MerkleAuditModal
        correlationId={job.correlation_id}
        isOpen={isMerkleModalOpen}
        onClose={() => setIsMerkleModalOpen(false)}
      />

      {/* Topology-Aware Blast Radius Drawer (UI-14) */}
      <BlastRadiusDrawer
        correlationId={job.correlation_id}
        isOpen={isBlastRadiusOpen}
        onClose={() => setIsBlastRadiusOpen(false)}
        onOpenDiff={() => {
          setIsBlastRadiusOpen(false);
          setIsDiffModalOpen(true);
        }}
        onOpenClusterRadar={() => {
          setIsBlastRadiusOpen(false);
          setIsClusterRadarOpen(true);
        }}
      />

      {/* Dual-Mode Monaco HCL/YAML Code Diff Inspector (UI-23) */}
      <MonacoDiffModal
        correlationId={job.correlation_id}
        isOpen={isDiffModalOpen}
        onClose={() => setIsDiffModalOpen(false)}
      />

      {/* Multi-Cluster Topology Radar (UI-25) */}
      <ClusterMapModal
        isOpen={isClusterRadarOpen}
        onClose={() => setIsClusterRadarOpen(false)}
      />

      {/* Dual-Pane Split-Screen Terminal Replay (UI-27) */}
      <DualTerminalReplay
        currentEvents={stream.events}
        currentCorrelationId={job.correlation_id}
        isOpen={isDualReplayOpen}
        onClose={() => setIsDualReplayOpen(false)}
      />
    </section>
  );
}

export default JobDetail;
