"use client";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useJobStream } from "@/hooks/useJobStream";
import { Terminal } from "./Terminal";
import { STATUS_STYLE } from "@/lib/types";
import type { Job } from "@/lib/types";
import { timeAgo } from "@/lib/util";

export function JobDetail({ job, currentUser, onChanged }: {
  job: Job | null; currentUser: string; onChanged: () => void;
}) {
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

  if (!job)
    return (
      <div className="flex h-full items-center justify-center bg-[#07090E] p-8 text-center text-sm text-slate-600">
        Select a task in the Task Monitor to see its status, live terminal, or approval deck.
      </div>
    );

  const status = liveStatus ?? job.status;
  const pending = status === "PENDING_APPROVAL";
  const isRequester = currentUser === job.requester_id;

  async function decide(kind: "approveJob" | "rejectJob") {
    setError(null);
    try { await api[kind](job!.id, currentUser); onChanged(); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col bg-[#07090E]">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-800/80 px-5 py-3">
        <span className="font-mono text-sm font-semibold text-cyan-400">{job.correlation_id}</span>
        <span className="text-sm text-slate-200">{job.name}</span>
        <span className={`rounded border px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status] ?? ""}`}>{status}</span>
        {job.servicenow_chg && (
          <span className="rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-400">ServiceNow · {job.servicenow_chg}</span>
        )}
        <span className="ml-auto text-xs text-slate-500">
          requester <span className="text-slate-300">{job.requester_id}</span>
          {job.approver_id ? <> · approver <span className="text-slate-300">{job.approver_id}</span></> : null}
        </span>
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {pending ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
            <h3 className="text-sm font-semibold text-amber-300">Approval required (Maker-Checker)</h3>
            <p className="mt-1 text-xs text-slate-400">
              High-risk change. A checker — a different person — must approve before execution.
              {job.servicenow_chg ? ` ServiceNow ticket ${job.servicenow_chg} is Awaiting Approval.` : ""}
            </p>
            <pre className="mt-3 overflow-x-auto rounded border border-slate-800 bg-[#05070B] p-3 font-mono text-xs text-slate-300">
              {JSON.stringify(job.parameters, null, 2)}
            </pre>
            {isRequester ? (
              <p className="mt-3 text-xs text-amber-400/90">
                🔒 Approve is disabled — you submitted this request. Separation of duties: requester ≠ approver.
              </p>
            ) : (
              <div className="mt-3 flex gap-2">
                <button onClick={() => decide("approveJob")}
                  className="rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500">
                  Approve &amp; Execute
                </button>
                <button onClick={() => decide("rejectJob")}
                  className="rounded-md bg-rose-600/90 px-4 py-1.5 text-sm font-medium text-white hover:bg-rose-500">
                  Reject
                </button>
              </div>
            )}
            {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
          </div>
        ) : (
          <>
            {job.diagnostic && status === "FAILED" && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4">
                <h3 className="text-sm font-semibold text-rose-300">⚠ Root Cause</h3>
                <p className="mt-1 text-xs text-slate-300">{job.diagnostic}</p>
                <button disabled title="Wired in Phase 2 (rollback adapter)"
                  className="mt-2 rounded-md border border-rose-500/50 px-3 py-1 text-xs text-rose-300 opacity-50">
                  Dispatch rollback playbook
                </button>
              </div>
            )}
            <div className="h-[50vh] min-h-[300px]">
              <Terminal events={stream.events} live={stream.live} />
            </div>
          </>
        )}

        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          <span>submitted {timeAgo(job.created_at)}</span>
          {job.approved_at && <span>approved {timeAgo(job.approved_at)}</span>}
          {job.completed_at && <span>completed {timeAgo(job.completed_at)}</span>}
          {job.exit_code !== null && <span>exit code {job.exit_code}</span>}
        </div>
      </div>
    </section>
  );
}
