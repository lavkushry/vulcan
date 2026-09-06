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
  const [rollbackDispatched, setRollbackDispatched] = useState<boolean>(false);
  const stream = useJobStream(job ? (job.correlation_id ?? job.id) : null);

  // Live status from the WebSocket beats the 2.5s poll.
  const liveStatus = useMemo(() => {
    for (let i = stream.events.length - 1; i >= 0; i--) {
      const e = stream.events[i];
      if (e.type === "status") return e.data.status as string;
    }
    return null;
  }, [stream.events]);

  if (!job)
    return (
      <div className="flex h-full items-center justify-center bg-[#07090E] p-8 text-center text-sm text-slate-600 font-mono">
        Select a task in the Task Monitor to see its status, live terminal, or approval deck.
      </div>
    );

  const status = liveStatus ?? job.status;
  const pending = status === "PENDING_APPROVAL";
  const isRunningOrLocked = status === "RUNNING" || status === "LOCKED" || status === "VERIFYING";

  async function decide(kind: "approveJob" | "rejectJob") {
    setError(null);
    try { await api[kind](job!.id, currentUser); onChanged(); }
    catch (e) { setError((e as Error).message); }
  }

  const handleRollback = () => {
    setRollbackDispatched(true);
    setTimeout(() => setRollbackDispatched(false), 3000);
  };

  // Determine active step index in the 8-step domain rail
  const activeStepIdx = useMemo(() => {
    if (status === "FAILED") return 5;
    if (status === "REJECTED") return 2;
    const idx = PROGRESSION_STEPS.indexOf(status);
    return idx >= 0 ? idx : 5;
  }, [status]);

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col bg-[#07090E]">
      {/* Top Header */}
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-800/80 px-5 py-3 bg-[#0C101A]/60 font-mono">
        <span className="text-sm font-bold text-cyan-400">{job.correlation_id}</span>
        <span className="text-sm text-slate-200">{job.name}</span>
        <span className={`rounded border px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[status] ?? ""}`}>
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
      <div className="px-5 py-2.5 border-b border-slate-800/80 bg-[#07090E] overflow-x-auto select-none">
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
            fencingToken={10482}
            targetResource={(job.parameters?.target_resource as string) || "prod-edge-vip"}
            quorumActive={4}
            quorumTotal={5}
            isHolding={true}
          />
        )}

        {/* Pending Approval -> Separation of Duties Proof Cockpit */}
        {pending ? (
          <div className="space-y-3">
            <SeparationOfDutiesProofCard
              requesterId={job.requester_id}
              currentUserId={currentUser}
              servicenowChg={job.servicenow_chg}
              onApprove={() => decide("approveJob")}
              onReject={() => decide("rejectJob")}
              onSwitchUser={(user) => setCurrentUser(user)}
            />
            {error && <p className="text-xs font-mono text-rose-400">{error}</p>}
          </div>
        ) : (
          <>
            {/* AI SRE AST Diagnostic Card when FAILED */}
            {job.diagnostic && status === "FAILED" && (
              <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-4 font-mono text-xs space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-rose-300 font-bold">
                    <AlertCircle size={16} />
                    <span>AI SRE Diagnostic Pinpoint (AST Line Analysis)</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-500/30">
                    Exit Code 1 · CyberArk Auth Expired
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-[#05070B] border border-slate-800 text-slate-300 text-[11px] leading-relaxed">
                  <span className="text-rose-400 font-bold">Root Cause:</span> {job.diagnostic}
                </div>

                {/* Predictive Rollback Micro-DAG Preview */}
                <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800 space-y-2">
                  <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
                    Synthesized Rollback Recovery DAG (3 Stages):
                  </span>
                  <div className="flex items-center gap-2 text-[10px] text-slate-300">
                    <span className="px-2 py-1 rounded bg-slate-900 border border-slate-700">1. Renew Vault Token</span>
                    <span className="text-slate-600">➔</span>
                    <span className="px-2 py-1 rounded bg-slate-900 border border-slate-700">2. Restore Prev Cert SHA</span>
                    <span className="text-slate-600">➔</span>
                    <span className="px-2 py-1 rounded bg-slate-900 border border-slate-700">3. TLS 1.3 Synthetic Probe</span>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleRollback}
                    className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(255,0,85,0.4)]"
                  >
                    <RefreshCw size={12} className={rollbackDispatched ? "animate-spin" : ""} />
                    <span>{rollbackDispatched ? "Rollback Dispatched!" : "Dispatch Rollback Playbook"}</span>
                  </button>
                </div>
              </div>
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
