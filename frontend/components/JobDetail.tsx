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
import { AlertCircle, RefreshCw } from "lucide-react";
import ASTFailurePinpointCard from "./ASTFailurePinpointCard";

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

            {/* Live Terminal */}
            <div className="h-[52vh] min-h-[320px]">
              <Terminal events={stream.events} live={stream.live} />
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
    </section>
  );
}

export default JobDetail;
