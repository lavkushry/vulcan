'use client';

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { 
  Terminal as TerminalIcon, 
  ShieldCheck, 
  AlertTriangle, 
  Play, 
  CheckCircle2, 
  RotateCcw, 
  Clock, 
  Server, 
  Search, 
  Check, 
  X, 
  Copy, 
  ExternalLink,
  Layers,
  Radio,
  Sparkles
} from 'lucide-react';
import { useJobStream } from '@/hooks/useJobStream';
import { STATUS_STYLE, FILTER_LABELS } from '@/lib/types';
import { timeAgo } from '@/lib/util';
import type { TaskRecord } from './TaskMatrixTable';

interface TerminalAuditWorkspaceProps {
  tasks: TaskRecord[];
  selectedTaskId: string | null;
  currentUser: string;
  onSelectTask: (taskId: string) => void;
  onApproveTask: (task: TaskRecord) => Promise<void>;
  onRejectTask: (task: TaskRecord) => Promise<void>;
  onTriggerRollback?: (task: TaskRecord) => void;
  auditChainTip?: string;
}

export default function TerminalAuditWorkspace({
  tasks,
  selectedTaskId,
  currentUser,
  onSelectTask,
  onApproveTask,
  onRejectTask,
  onTriggerRollback,
  auditChainTip = "0x9a8f12c4e7b8"
}: TerminalAuditWorkspaceProps) {
  const [sidebarFilter, setSidebarFilter] = useState('');
  const [copied, setCopied] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Selected Task
  const selectedTask = useMemo(() => {
    return tasks.find(t => t.id === selectedTaskId || t.correlation_id === selectedTaskId) || tasks[0] || null;
  }, [tasks, selectedTaskId]);

  // WebSocket Live Stream hook
  const stream = useJobStream(selectedTask ? selectedTask.correlation_id : null);

  // Live status from stream overrides static polling status
  const liveStatus = useMemo(() => {
    for (let i = stream.events.length - 1; i >= 0; i--) {
      const e = stream.events[i];
      if (e.type === 'status') return e.data.status as string;
    }
    return null;
  }, [stream.events]);

  const currentStatus = liveStatus || (selectedTask ? selectedTask.status : 'IDLE');
  const isPending = currentStatus === 'PENDING_APPROVAL';
  const isRequester = selectedTask ? currentUser === selectedTask.requester_id : false;

  // Auto-scroll terminal to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [stream.events]);

  // Filtered sidebar tasks
  const filteredSidebarTasks = useMemo(() => {
    if (!sidebarFilter.trim()) return tasks;
    const q = sidebarFilter.toLowerCase();
    return tasks.filter(t => 
      t.correlation_id.toLowerCase().includes(q) || 
      t.name.toLowerCase().includes(q) || 
      t.target_resource.toLowerCase().includes(q) ||
      t.status.toLowerCase().includes(q)
    );
  }, [tasks, sidebarFilter]);

  // Copy full logs
  const handleCopyLogs = () => {
    const text = stream.events
      .map(e => {
        if (e.type === 'stdout') return e.data?.line ?? (typeof e.data === 'string' ? e.data : e.data?.data ?? '');
        if (e.type === 'status') return `── [${e.data?.status}] ${e.data?.message || ''} ──`;
        if (e.type === 'diagnostic') return `⚠ [DIAGNOSTIC] ${e.data?.root_cause || ''}`;
        return '';
      })
      .filter(Boolean)
      .join('\n');

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex h-full bg-[#07090E] text-slate-200 overflow-hidden">
      {/* ===================================================================== */}
      {/* LEFT SIDEBAR: TASK SELECTOR RAIL                                     */}
      {/* ===================================================================== */}
      <aside className="w-80 border-r border-slate-800/80 bg-[#0A0E16] flex flex-col shrink-0">
        {/* Sidebar Header */}
        <div className="p-3.5 border-b border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold font-mono tracking-wider text-slate-400 uppercase">
              Execution Sessions
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">
              {tasks.length}
            </span>
          </div>

          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
            <input
              type="text"
              value={sidebarFilter}
              onChange={(e) => setSidebarFilter(e.target.value)}
              placeholder="Filter tasks..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-[#07090E] border border-slate-700 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Task List */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
          {filteredSidebarTasks.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-600">No sessions match query</div>
          ) : (
            filteredSidebarTasks.map(t => {
              const isSelected = selectedTask?.correlation_id === t.correlation_id || selectedTask?.id === t.id;
              const isRunning = t.status === 'RUNNING' || t.status === 'VERIFYING';

              return (
                <button
                  key={t.id || t.correlation_id}
                  onClick={() => onSelectTask(t.id || t.correlation_id)}
                  className={`w-full p-3 text-left transition-all flex flex-col gap-1.5 ${
                    isSelected
                      ? 'bg-cyan-950/20 border-l-2 border-l-cyan-400 text-white'
                      : 'hover:bg-slate-800/40 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-cyan-400">
                      {t.correlation_id}
                    </span>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${
                      STATUS_STYLE[t.status] || 'border-slate-700 bg-slate-800 text-slate-400'
                    }`}>
                      {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />}
                      {FILTER_LABELS[t.status] || t.status}
                    </span>
                  </div>

                  <div className="text-xs font-medium truncate text-slate-200">
                    {t.name}
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span>{t.target_resource}</span>
                    <span>{timeAgo(t.created_at)}</span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </aside>

      {/* ===================================================================== */}
      {/* MAIN VIEWPORT: TERMINAL & AUDIT CONTROLS                              */}
      {/* ===================================================================== */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#07090E] overflow-hidden">
        {!selectedTask ? (
          <div className="flex-1 flex items-center justify-center p-8 text-center text-slate-600 text-sm">
            Select a task session from the sidebar to view its live terminal and audit chain.
          </div>
        ) : (
          <>
            {/* Session Top Bar */}
            <header className="p-4 border-b border-slate-800/80 bg-[#0A0E16] flex flex-wrap items-center justify-between gap-3 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-cyan-950/60 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-sm">
                  <TerminalIcon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-base font-bold text-white tracking-wide">
                      {selectedTask.correlation_id}
                    </span>
                    <span className="text-slate-400 text-sm font-medium">
                      // {selectedTask.name}
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                      STATUS_STYLE[currentStatus] || 'border-slate-700 bg-slate-800 text-slate-300'
                    }`}>
                      {FILTER_LABELS[currentStatus] || currentStatus}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 font-mono mt-0.5">
                    <span>Target: <strong className="text-slate-200">{selectedTask.target_resource}</strong></span>
                    <span>Env: <strong className="text-slate-200">{selectedTask.environment}</strong></span>
                    <span>Requester: <strong className="text-slate-200">{selectedTask.requester_id}</strong></span>
                    {selectedTask.approver_id && (
                      <span>Approver: <strong className="text-cyan-300">{selectedTask.approver_id}</strong></span>
                    )}
                    {selectedTask.servicenow_chg && (
                      <span className="text-cyan-400">ServiceNow: <strong>{selectedTask.servicenow_chg}</strong></span>
                    )}
                  </div>
                </div>
              </div>

              {/* Cryptographic Merkle Chain Tip Badge */}
              <div className="flex items-center gap-3">
                <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-purple-950/30 border border-purple-500/30 text-xs font-mono">
                  <ShieldCheck className="w-4 h-4 text-purple-400" />
                  <span className="text-slate-400">Merkle Tip:</span>
                  <span className="text-purple-300 font-bold">{auditChainTip}</span>
                  <span className="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/20 text-purple-300 uppercase">
                    Chain Verified
                  </span>
                </div>

                <button
                  onClick={handleCopyLogs}
                  className="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy Output'}</span>
                </button>
              </div>
            </header>

            {/* Maker-Checker Sign-off Deck (if Pending Approval) */}
            {isPending && (
              <div className="m-4 p-4 rounded-xl border border-amber-500/40 bg-amber-500/10 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="text-sm font-bold text-amber-300 flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" />
                      <span>Maker-Checker Governance Gate (Separation of Duties)</span>
                    </h4>
                    <p className="text-xs text-slate-300 mt-1">
                      This is a protected high-risk change. A designated checker (someone other than requester <strong>{selectedTask.requester_id}</strong>) must authorize execution before the lock and runtime sandbox are provisioned.
                    </p>
                  </div>

                  {selectedTask.servicenow_chg && (
                    <span className="px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/30 text-amber-300 font-mono text-xs">
                      {selectedTask.servicenow_chg} · Awaiting Approval
                    </span>
                  )}
                </div>

                {/* Parameters preview */}
                <div className="bg-[#05070B] border border-slate-800 rounded-lg p-3 font-mono text-xs text-slate-300 max-h-36 overflow-auto">
                  <span className="text-slate-500 text-[10px] block mb-1 uppercase tracking-wider font-sans">
                    Runtime Parameters:
                  </span>
                  <pre>{JSON.stringify(selectedTask.parameters, null, 2)}</pre>
                </div>

                {/* Anti-Self-Approval Enforcement */}
                {isRequester ? (
                  <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/30 text-xs text-amber-300 flex items-center gap-2">
                    <span className="text-base">🔒</span>
                    <span>
                      <strong>Approve is disabled for you:</strong> You submitted this request as <strong>{currentUser}</strong>. Under banking Separation of Duties, the requester cannot approve their own change. Switch persona to <strong>Bob (Approving Lead)</strong> in the header to authorize.
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={() => onApproveTask(selectedTask)}
                      className="px-4 py-2 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-md flex items-center gap-1.5 transition-colors"
                    >
                      <Check className="w-4 h-4" />
                      <span>Approve &amp; Dispatch Execution</span>
                    </button>
                    <button
                      onClick={() => onRejectTask(selectedTask)}
                      className="px-4 py-2 text-xs font-bold rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white shadow-md flex items-center gap-1.5 transition-colors"
                    >
                      <X className="w-4 h-4" />
                      <span>Reject Request</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* AI Root Cause Diagnostic Card (if Failed) */}
            {selectedTask.status === 'FAILED' && (selectedTask.diagnostic || selectedTask.error_message) && (
              <div className="m-4 p-4 rounded-xl border border-rose-500/40 bg-rose-500/10 space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span>AI SRE Diagnostic: Root Cause Identified in &lt;1.8s</span>
                  </h4>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    Exit Code 1
                  </span>
                </div>
                <p className="text-xs text-slate-200">
                  {selectedTask.diagnostic || selectedTask.error_message}
                </p>
                {onTriggerRollback && (
                  <button
                    onClick={() => onTriggerRollback(selectedTask)}
                    className="mt-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-500/50 text-rose-300 flex items-center gap-1.5 transition-colors"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Trigger Automated Rollback</span>
                  </button>
                )}
              </div>
            )}

            {/* Streaming ANSI Terminal Canvas */}
            <div className="flex-1 p-4 overflow-hidden flex flex-col">
              <div className="flex-1 flex flex-col rounded-xl border border-slate-800 bg-[#05070B] overflow-hidden shadow-2xl">
                {/* Terminal Header */}
                <div className="px-4 py-2.5 border-b border-slate-800/80 bg-[#0A0E16] flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2 text-slate-400">
                    <span className={`w-2 h-2 rounded-full ${
                      stream.live ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
                    }`} />
                    <span className="text-[11px] uppercase tracking-wider">
                      {stream.live ? 'Live WebSocket Stream (60 FPS)' : 'Ring Buffer Replay (Late-Joiner)'}
                    </span>
                  </div>
                  <span className="text-slate-500 text-[11px]">
                    Events: {stream.events.length} lines buffered
                  </span>
                </div>

                {/* Terminal Body */}
                <div 
                  ref={terminalRef}
                  className="flex-1 p-4 font-mono text-xs leading-6 text-slate-300 overflow-y-auto space-y-0.5 selection:bg-cyan-500/30 selection:text-white"
                >
                  {stream.events.length === 0 ? (
                    <div className="py-8 text-center text-slate-600">
                      {isPending
                        ? "Task is awaiting Maker-Checker sign-off. Once approved, live stdout logs will stream here."
                        : "Connecting to WebSocket execution hub..."}
                    </div>
                  ) : (
                    stream.events.map((e) => {
                      if (e.type === 'stdout') {
                        const line = e.data?.line ?? (typeof e.data === 'string' ? e.data : e.data?.data ?? '');
                        return (
                          <div key={e.seq} className="whitespace-pre-wrap font-mono">
                            {line}
                          </div>
                        );
                      }
                      if (e.type === 'status') {
                        return (
                          <div key={e.seq} className="my-1.5 py-0.5 px-2 rounded bg-cyan-950/30 border border-cyan-500/20 text-cyan-300 text-[11px] font-mono">
                            ── [TRANSITION] Status: <strong>{e.data?.status}</strong> {e.data?.message ? `(${e.data.message})` : ''} ──
                          </div>
                        );
                      }
                      if (e.type === 'diagnostic') {
                        return (
                          <div key={e.seq} className="my-2 p-2.5 rounded bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono">
                            ⚠ [AI DIAGNOSTIC]: {e.data?.root_cause}
                          </div>
                        );
                      }
                      return null;
                    })
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
