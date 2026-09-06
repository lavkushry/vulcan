"use client";
import type { Job, JobStatus } from "@/lib/types";
import { FILTER_LABELS, STATUS_STYLE } from "@/lib/types";
import { timeAgo } from "@/lib/util";

const FILTERS: (JobStatus | "ALL")[] = [
  "ALL", "PENDING_APPROVAL", "QUEUED", "RUNNING", "VERIFYING", "SUCCESS", "FAILED", "REJECTED", "TIMEOUT_DENIED",
];

export function TaskMonitor({ jobs, allJobs, selectedId, onSelect, statusFilter, setStatusFilter, query, setQuery, onOpenFullMatrix }: {
  jobs: Job[]; allJobs: Job[]; selectedId: string | null; onSelect: (id: string) => void;
  statusFilter: JobStatus | "ALL"; setStatusFilter: (s: JobStatus | "ALL") => void;
  query: string; setQuery: (q: string) => void;
  onOpenFullMatrix?: () => void;
}) {
  const count = (s: JobStatus | "ALL") =>
    s === "ALL" ? allJobs.length : allJobs.filter((j) => j.status === s).length;

  return (
    <section className="flex h-full min-h-0 w-[320px] xl:w-[360px] shrink-0 flex-col border-r border-slate-800/80 bg-[#0A0E16]">
      <header className="border-b border-slate-800/80 px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">Task Monitor</h2>
          {onOpenFullMatrix && (
            <button
              onClick={onOpenFullMatrix}
              className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline underline-offset-2 flex items-center gap-1"
              title="Open full-width sortable Task Matrix table with CSV export"
            >
              Full Table &amp; CSV &rarr;
            </button>
          )}
        </div>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="filter: id, playbook, CHG…"
          className="mt-2 w-full rounded-md border border-slate-700 bg-[#07090E] px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:border-cyan-600 focus:outline-none" />
      </header>

      <div className="flex flex-wrap gap-1.5 border-b border-slate-800/80 px-3 py-2">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setStatusFilter(f)}
            className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${
              statusFilter === f ? "border-cyan-500/60 bg-cyan-500/15 text-cyan-300"
                                 : "border-slate-700 text-slate-400 hover:border-slate-500"}`}>
            {FILTER_LABELS[f]} <span className="opacity-60">{count(f)}</span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        {jobs.length === 0 && <div className="p-4 text-xs text-slate-600">No tasks match the current filter.</div>}
        {jobs.map((j) => (
          <button key={j.id} onClick={() => onSelect(j.id)}
            className={`w-full border-b border-slate-800/60 px-3 py-2.5 text-left hover:bg-slate-800/30 ${
              selectedId === j.id ? "border-l-2 border-l-cyan-500 bg-slate-800/50" : ""}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs text-cyan-400">{j.correlation_id}</span>
              <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS_STYLE[j.status]}`}>{j.status}</span>
            </div>
            <div className="mt-1 truncate text-xs text-slate-300">{j.name}</div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-slate-500">
              <span>{j.engine}</span>·<span>{j.requester_id}</span>
              {j.servicenow_chg ? <>·<span>{j.servicenow_chg}</span></> : null}
              <span className="ml-auto">{timeAgo(j.created_at)}</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
