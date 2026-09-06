'use client';

import React, { useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Search, Filter, Download, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle, Clock, Play, AlertTriangle, Ban, Timer
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useVulcan } from '@/lib/context';
import { api, DEMO_USERS } from '@/lib/api';
import type { Job, JobStatus } from '@/lib/types';
import { STATUS_STYLE } from '@/lib/types';
import { useJobStream } from '@/hooks/useJobStream';

const STATUS_ICON: Record<string, React.ReactNode> = {
  PENDING_APPROVAL: <Clock size={14} className="text-amber-400" />,
  QUEUED: <Clock size={14} className="text-blue-400" />,
  RUNNING: <Play size={14} className="text-cyan-400 animate-pulse" />,
  VERIFYING: <AlertTriangle size={14} className="text-amber-400" />,
  SUCCESS: <CheckCircle2 size={14} className="text-emerald-400" />,
  FAILED: <XCircle size={14} className="text-rose-400" />,
  REJECTED: <Ban size={14} className="text-slate-500" />,
  TIMEOUT_DENIED: <Timer size={14} className="text-orange-400" />,
};

const FILTER_OPTIONS: { key: JobStatus | 'ALL'; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'PENDING_APPROVAL', label: 'Pending' },
  { key: 'RUNNING', label: 'Running' },
  { key: 'SUCCESS', label: 'Success' },
  { key: 'FAILED', label: 'Failed' },
  { key: 'REJECTED', label: 'Rejected' },
];

const PAGE_SIZE = 20;

function HistoryContent() {
  const { currentUser } = useVulcan();
  const searchParams = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('selected'));
  const [page, setPage] = useState(0);

  useEffect(() => {
    const sel = searchParams.get('selected');
    if (sel) setSelectedId(sel);
  }, [searchParams]);

  // Poll jobs
  useEffect(() => {
    const refresh = async () => {
      try { setJobs(await api.listJobs()); } catch { /* */ }
    };
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  // Filter + search
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return jobs.filter((j) => {
      if (statusFilter !== 'ALL' && j.status !== statusFilter) return false;
      if (!q) return true;
      return `${j.correlation_id} ${j.identifier} ${j.name} ${j.requester_id} ${j.servicenow_chg ?? ''}`.toLowerCase().includes(q);
    }).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [jobs, statusFilter, searchQuery]);

  // Paginated
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = useMemo(() => filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE), [filtered, page]);

  // Status counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: jobs.length };
    jobs.forEach((j) => { counts[j.status] = (counts[j.status] || 0) + 1; });
    return counts;
  }, [jobs]);

  // Selected job
  const selectedJob = useMemo(() => jobs.find((j) => j.correlation_id === selectedId) ?? null, [jobs, selectedId]);

  // WebSocket stream for selected job
  const { events: wsEvents, live: wsLive } = useJobStream(
    selectedJob && (selectedJob.status === 'RUNNING' || selectedJob.status === 'VERIFYING') ? selectedJob.correlation_id : null
  );

  // Approve / Reject handlers
  const handleApprove = useCallback(async () => {
    if (!selectedId) return;
    try {
      await api.approveJob(selectedId, currentUser);
      const refreshed = await api.listJobs();
      setJobs(refreshed);
    } catch (e: any) {
      alert(e?.message || 'Approval failed');
    }
  }, [selectedId, currentUser]);

  const handleReject = useCallback(async () => {
    if (!selectedId) return;
    try {
      await api.rejectJob(selectedId, currentUser);
      const refreshed = await api.listJobs();
      setJobs(refreshed);
    } catch (e: any) {
      alert(e?.message || 'Rejection failed');
    }
  }, [selectedId, currentUser]);

  // Time ago helper
  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return `${Math.floor(diff / 86_400_000)}d ago`;
  };

  // CSV Export
  const exportCSV = useCallback(() => {
    const header = 'Correlation ID,Action,Engine,Risk,Status,Requester,Approver,CHG,Created\n';
    const rows = filtered.map((j) =>
      `${j.correlation_id},${j.identifier},${j.engine},${j.risk_tier},${j.status},${j.requester_id},${j.approver_id ?? ''},${j.servicenow_chg ?? ''},${j.created_at}`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `vulcan-history-${Date.now()}.csv`; a.click();
    URL.revokeObjectURL(url);
  }, [filtered]);

  return (
    <div className="flex h-full">
      {/* ──── MASTER: Execution List ──── */}
      <div className="w-[400px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/30">
        {/* Search */}
        <div className="px-3 py-2.5 border-b border-glass-border">
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-glass-surface border border-glass-border">
            <Search size={14} className="text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
              placeholder="Search by ID, playbook, CHG, host…"
              className="flex-1 bg-transparent text-xs text-slate-300 placeholder-slate-600 outline-none"
            />
          </div>
        </div>

        {/* Status filter pills */}
        <div className="px-3 py-2 border-b border-glass-border flex flex-wrap gap-1.5">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => { setStatusFilter(opt.key); setPage(0); }}
              className={`text-[10px] font-mono px-2 py-1 rounded-full border transition-colors ${
                statusFilter === opt.key
                  ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
                  : 'border-glass-border bg-glass-surface text-slate-500 hover:text-slate-300'
              }`}
            >
              {opt.label}
              {statusCounts[opt.key] !== undefined && (
                <span className="ml-1 opacity-60">{statusCounts[opt.key]}</span>
              )}
            </button>
          ))}
        </div>

        {/* Execution cards */}
        <div className="flex-1 overflow-y-auto">
          {paginated.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-slate-600">No executions found</div>
          )}
          {paginated.map((job) => (
            <button
              key={job.correlation_id}
              onClick={() => setSelectedId(job.correlation_id)}
              className={`w-full text-left px-3 py-3 border-b border-glass-border/50 transition-colors relative ${
                selectedId === job.correlation_id
                  ? 'bg-cyan-500/[0.06]'
                  : 'hover:bg-white/[0.02]'
              }`}
            >
              {selectedId === job.correlation_id && (
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
              )}
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {STATUS_ICON[job.status]}
                  <span className="text-[11px] font-mono text-slate-400">{job.correlation_id}</span>
                </div>
                <span className="text-[10px] text-slate-600">{timeAgo(job.created_at)}</span>
              </div>
              <div className="text-xs text-slate-300 mb-1 truncate">{job.name}</div>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="font-mono text-slate-600">{job.engine}</span>
                <span className="text-slate-700">·</span>
                <span className="text-slate-600">{job.requester_id}</span>
                <span className={`ml-auto w-1.5 h-1.5 rounded-full ${
                  job.risk_tier === 'HIGH' ? 'bg-rose-400' :
                  job.risk_tier === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400'
                }`} />
              </div>
            </button>
          ))}
        </div>

        {/* Pagination + Export */}
        <div className="px-3 py-2 border-t border-glass-border flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <button
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className="p-1 rounded text-slate-500 hover:text-slate-300 disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-[10px] font-mono text-slate-600">
              {page + 1} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(page + 1)}
              className="p-1 rounded text-slate-500 hover:text-slate-300 disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 text-[10px] text-slate-500 hover:text-cyan-400 transition-colors"
          >
            <Download size={12} />
            CSV
          </button>
        </div>
      </div>

      {/* ──── DETAIL: Execution Detail ──── */}
      <div className="flex-1 overflow-y-auto p-5">
        {!selectedJob ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600">
            <Clock size={40} className="mb-3 opacity-30" />
            <p className="text-sm">Select an execution to view details</p>
            <p className="text-xs mt-1 text-slate-700">Or press ⌘K to run a new action</p>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto space-y-5">
            {/* Header */}
            <div>
              <div className="flex items-center gap-3 mb-2">
                {STATUS_ICON[selectedJob.status]}
                <h2 className="text-lg font-semibold text-slate-200">{selectedJob.name}</h2>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <span className={`px-2 py-1 rounded-md border font-mono text-[11px] ${STATUS_STYLE[selectedJob.status]}`}>
                  {selectedJob.status}
                </span>
                <span className="text-slate-600 font-mono">{selectedJob.correlation_id}</span>
                <span className="text-slate-700">·</span>
                <span className="px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/50 font-mono text-slate-400">
                  {selectedJob.engine}
                </span>
                <span className={`px-1.5 py-0.5 rounded border font-mono ${
                  selectedJob.risk_tier === 'HIGH' ? 'border-rose-500/30 text-rose-400 bg-rose-500/10' :
                  selectedJob.risk_tier === 'MEDIUM' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                  'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                }`}>
                  {selectedJob.risk_tier}
                </span>
              </div>
            </div>

            {/* Metadata card */}
            <div className="bg-glass-surface border border-glass-border rounded-lg p-4 space-y-2">
              <h3 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">Execution Info</h3>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-600">Requester</span>
                  <div className="text-slate-300 font-mono mt-0.5">{selectedJob.requester_id}</div>
                </div>
                <div>
                  <span className="text-slate-600">Approver</span>
                  <div className="text-slate-300 font-mono mt-0.5">{selectedJob.approver_id ?? '—'}</div>
                </div>
                <div>
                  <span className="text-slate-600">ServiceNow CHG</span>
                  <div className="text-slate-300 font-mono mt-0.5">{selectedJob.servicenow_chg ?? '—'}</div>
                </div>
                <div>
                  <span className="text-slate-600">Submitted</span>
                  <div className="text-slate-300 font-mono mt-0.5">{timeAgo(selectedJob.created_at)}</div>
                </div>
                {selectedJob.exit_code !== null && (
                  <div>
                    <span className="text-slate-600">Exit Code</span>
                    <div className={`font-mono mt-0.5 ${selectedJob.exit_code === 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {selectedJob.exit_code}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Parameters card */}
            <div className="bg-glass-surface border border-glass-border rounded-lg p-4">
              <h3 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">Parameters</h3>
              <pre className="text-xs font-mono text-slate-400 bg-canvas-void rounded-lg p-3 overflow-x-auto">
                {JSON.stringify(selectedJob.parameters, null, 2)}
              </pre>
            </div>

            {/* Approval Deck — when PENDING_APPROVAL */}
            {selectedJob.status === 'PENDING_APPROVAL' && (
              <div className="bg-glass-surface border border-amber-500/20 rounded-lg p-4">
                <h3 className="text-xs font-mono text-amber-400/70 uppercase tracking-wider mb-3">Maker-Checker Approval</h3>
                {currentUser === selectedJob.requester_id ? (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-amber-400/70">
                      <AlertTriangle size={14} />
                      <span>You submitted this request. Separation of Duties: requester ≠ approver.</span>
                    </div>
                    <p className="text-xs text-slate-500">Switch to another persona to approve or reject.</p>
                    <div className="flex gap-2 mt-3">
                      <button disabled className="px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-500/40 text-xs font-mono cursor-not-allowed opacity-50">
                        Approve & Execute
                      </button>
                      <button disabled className="px-4 py-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-500/40 text-xs font-mono cursor-not-allowed opacity-50">
                        Reject
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-slate-400">
                      Requested by <span className="text-cyan-400 font-mono">{selectedJob.requester_id}</span>. 
                      You are acting as <span className="text-emerald-400 font-mono">{currentUser}</span>.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={handleApprove}
                        className="px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-mono hover:bg-emerald-500/30 transition-colors"
                      >
                        ✓ Approve & Execute
                      </button>
                      <button
                        onClick={handleReject}
                        className="px-4 py-2 rounded-lg bg-rose-500/20 border border-rose-500/30 text-rose-400 text-xs font-mono hover:bg-rose-500/30 transition-colors"
                      >
                        ✗ Reject
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Live Terminal — when RUNNING */}
            {(selectedJob.status === 'RUNNING' || selectedJob.status === 'VERIFYING') && (
              <div className="bg-glass-surface border border-cyan-500/20 rounded-lg overflow-hidden">
                <div className="px-4 py-2 border-b border-glass-border flex items-center justify-between">
                  <h3 className="text-xs font-mono text-cyan-400/70 uppercase tracking-wider">Live Terminal</h3>
                  <div className="flex items-center gap-2">
                    {wsLive && <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />}
                    <span className="text-[10px] font-mono text-slate-500">{wsLive ? 'CONNECTED' : 'CONNECTING…'}</span>
                  </div>
                </div>
                <div className="bg-canvas-void p-3 font-mono text-xs text-slate-400 max-h-[300px] overflow-y-auto">
                  {wsEvents.filter((e) => e.type === 'stdout').map((e, i) => (
                    <div key={i} className="whitespace-pre-wrap">{typeof e.data === 'string' ? e.data : e.data?.line ?? JSON.stringify(e.data)}</div>
                  ))}
                  {wsEvents.length === 0 && (
                    <div className="text-slate-600 animate-pulse">Waiting for output…</div>
                  )}
                </div>
              </div>
            )}

            {/* Diagnostic — when FAILED */}
            {selectedJob.status === 'FAILED' && selectedJob.diagnostic && (
              <div className="bg-glass-surface border border-rose-500/20 rounded-lg p-4">
                <h3 className="text-xs font-mono text-rose-400/70 uppercase tracking-wider mb-3">AI Root-Cause Diagnostic</h3>
                <pre className="text-xs font-mono text-rose-300/80 bg-canvas-void rounded-lg p-3 whitespace-pre-wrap">
                  {selectedJob.diagnostic}
                </pre>
              </div>
            )}

            {/* Success output — completed_at */}
            {selectedJob.status === 'SUCCESS' && selectedJob.completed_at && (
              <div className="bg-glass-surface border border-emerald-500/20 rounded-lg p-4">
                <h3 className="text-xs font-mono text-emerald-400/70 uppercase tracking-wider mb-3">Execution Complete</h3>
                <div className="text-xs text-slate-400 space-y-1">
                  <div>Completed: <span className="font-mono text-emerald-400">{timeAgo(selectedJob.completed_at)}</span></div>
                  {selectedJob.approved_at && <div>Approved: <span className="font-mono text-slate-300">{timeAgo(selectedJob.approved_at)}</span></div>}
                  <div>Exit code: <span className="font-mono text-emerald-400">{selectedJob.exit_code}</span></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function HistoryPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="flex-1 flex items-center justify-center text-xs text-slate-500 font-mono">Loading Execution History…</div>}>
        <HistoryContent />
      </Suspense>
    </AppShell>
  );
}
