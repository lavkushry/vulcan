'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef, Suspense } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import ChatAssistant, { ChatLaunchPayload } from '@/components/ChatAssistant';
import { AgentControlCenter } from '@/components/AgentControlCenter';
import { TaskMonitor } from '@/components/TaskMonitor';
import { JobDetail } from '@/components/JobDetail';
import { ResizableDualPane } from '@/components/ResizableDualPane';
import { KeyboardShortcutsModal } from '@/components/KeyboardShortcutsModal';
import { useKeyboardHotkeys } from '@/hooks/useKeyboardHotkeys';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';
import type { Job, JobStatus } from '@/lib/types';
import { useRouter, useSearchParams } from 'next/navigation';
import { Table2, ArrowRight, Keyboard, Bot, MessageSquare } from 'lucide-react';

function ChatConsoleContent() {
  const { currentUser } = useVulcan();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialMode = searchParams?.get('mode') === 'agents' ? 'agents' : 'chat';
  const [requestMode, setRequestMode] = useState<'chat' | 'agents'>(initialMode);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'ALL'>('ALL');
  const [query, setQuery] = useState('');
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const refreshJobs = useCallback(async () => {
    try {
      const data = await api.listJobs(currentUser);
      setJobs(data);
    } catch {
      /* ignore */
    }
  }, [currentUser]);

  useEffect(() => {
    refreshJobs();
    const t = setInterval(refreshJobs, 2500);
    return () => clearInterval(t);
  }, [refreshJobs]);

  const filteredJobs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((j) => {
      if (statusFilter !== 'ALL' && j.status !== statusFilter) return false;
      if (!q) return true;
      return (
        j.correlation_id.toLowerCase().includes(q) ||
        j.name.toLowerCase().includes(q) ||
        j.identifier.toLowerCase().includes(q) ||
        (j.servicenow_chg && j.servicenow_chg.toLowerCase().includes(q))
      );
    });
  }, [jobs, statusFilter, query]);

  const selectedJob = useMemo(
    () => jobs.find((j) => j.id === selectedId || j.correlation_id === selectedId) ?? null,
    [jobs, selectedId]
  );

  // Keyboard navigation through task list
  const handleNextTask = useCallback(() => {
    if (filteredJobs.length === 0) return;
    const currIdx = filteredJobs.findIndex((j) => j.id === selectedId || j.correlation_id === selectedId);
    const nextIdx = currIdx < filteredJobs.length - 1 ? currIdx + 1 : 0;
    setSelectedId(filteredJobs[nextIdx].id);
  }, [filteredJobs, selectedId]);

  const handlePrevTask = useCallback(() => {
    if (filteredJobs.length === 0) return;
    const currIdx = filteredJobs.findIndex((j) => j.id === selectedId || j.correlation_id === selectedId);
    const prevIdx = currIdx > 0 ? currIdx - 1 : filteredJobs.length - 1;
    setSelectedId(filteredJobs[prevIdx].id);
  }, [filteredJobs, selectedId]);

  const handleExecuteOrApprove = useCallback(async () => {
    if (selectedJob && selectedJob.status === 'PENDING_APPROVAL' && Boolean(selectedJob.capabilities?.can_approve)) {
      try {
        await api.approveJob(selectedJob.id, currentUser);
        refreshJobs();
      } catch {
        /* ignore */
      }
    }
  }, [selectedJob, currentUser, refreshJobs]);

  // Hook Linear-style hotkeys
  useKeyboardHotkeys({
    onNextItem: handleNextTask,
    onPrevItem: handlePrevTask,
    onExecuteOrApprove: handleExecuteOrApprove,
    onFocusSearch: () => searchInputRef.current?.focus(),
    onDismiss: () => setIsHelpOpen(false),
    onToggleHelp: () => setIsHelpOpen((prev) => !prev),
  });

  // Dispatch handler called when user clicks "Launch Action" inside Chat
  const handleDispatchTask = useCallback(
    async (payload: ChatLaunchPayload) => {
      const p: Record<string, unknown> = {
        ...payload.parameters,
        environment: payload.environment,
        target_resource: payload.target_resource_id,
        dry_run: payload.dry_run ?? false,
      };

      const created = await api.createJob({
        identifier: payload.catalog_identifier,
        parameters: p,
        requester_id: payload.requester_id || currentUser,
        servicenow_chg: payload.servicenow_chg || null,
      });

      // Instantly refresh, open detail inspector, and select this new job
      await refreshJobs();
      setSelectedId(created.id);
      setShowDetails(true);
      return created;
    },
    [currentUser, refreshJobs]
  );

  const handleSelectTask = useCallback((corrId: string) => {
    setSelectedId(corrId);
    setShowDetails(true);
  }, []);

  // Left Pane component
  const leftPaneContent = (
    <div className="h-full flex flex-col bg-canvas-void">
      <div className="px-4 py-2 border-b border-glass-border flex items-center justify-between bg-glass-surface/40 select-none">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 p-0.5 rounded-lg bg-slate-900 border border-glass-border text-xs font-mono">
            <button
              type="button"
              onClick={() => setRequestMode('chat')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-all ${
                requestMode === 'chat'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <MessageSquare size={12} className="text-cyan-400" />
              <span>Copilot Chat</span>
            </button>
            <button
              type="button"
              onClick={() => setRequestMode('agents')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded transition-all ${
                requestMode === 'agents'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Bot size={12} className="text-cyan-400" />
              <span>Autonomous AgentOS</span>
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            className={`text-[10px] font-mono px-2 py-1 rounded border transition-colors flex items-center gap-1.5 ${
              showDetails
                ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300'
                : 'border-glass-border hover:border-slate-600 bg-white/[0.02] text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>{showDetails ? 'Focus View' : `Inspect Details (${jobs.length})`}</span>
          </button>
          <button
            type="button"
            onClick={() => setIsHelpOpen(true)}
            className="text-[10px] font-mono text-slate-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
            title="Press '?' for hotkeys"
          >
            <Keyboard size={12} />
            <span>Hotkeys</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {requestMode === 'chat' ? (
          <ChatAssistant
            currentUser={currentUser}
            onDispatchTask={handleDispatchTask}
            onSelectTaskToView={handleSelectTask}
          />
        ) : (
          <div className="h-full overflow-y-auto">
            <AgentControlCenter />
          </div>
        )}
      </div>
    </div>
  );

  // Right Pane component
  const rightPaneContent = (
    <div className="h-full flex flex-col bg-glass-surface/30">
      <div className="px-4 py-2 border-b border-glass-border flex items-center justify-between bg-glass-surface/60 select-none">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
            Request Details &amp; Execution Output
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/history')}
            className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
          >
            <Table2 size={12} />
            <span>Activity History</span>
            <ArrowRight size={10} />
          </button>
          <button
            onClick={() => setShowDetails(false)}
            className="text-xs text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-white/[0.04]"
            title="Close details pane"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Compact Task List */}
        <div className="w-[240px] flex-shrink-0 border-r border-glass-border overflow-hidden">
          <TaskMonitor
            jobs={filteredJobs}
            allJobs={jobs}
            selectedId={selectedId}
            onSelect={setSelectedId}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            query={query}
            setQuery={setQuery}
            onOpenFullMatrix={() => router.push('/history')}
          />
        </div>

        {/* Live Terminal & Approval Inspector */}
        <div className="flex-1 overflow-hidden">
          <JobDetail
            job={selectedJob}
            currentUser={currentUser}
            onChanged={refreshJobs}
          />
        </div>
      </div>
    </div>
  );

  return (
    <div className="relative h-full overflow-hidden">
      {showDetails ? (
        <ResizableDualPane
          leftPane={leftPaneContent}
          rightPane={rightPaneContent}
          defaultRatio={0.50}
          minRatio={0.25}
          maxRatio={0.75}
          storageKey="vulcan_chat_split_ratio"
        />
      ) : (
        <div className="h-full max-w-5xl mx-auto border-x border-glass-border shadow-2xl">
          {leftPaneContent}
        </div>
      )}

      <KeyboardShortcutsModal
        isOpen={isHelpOpen}
        onClose={() => setIsHelpOpen(false)}
      />
    </div>
  );
}

export default function ChatPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-center text-slate-500 font-mono text-xs">Loading request console…</div>}>
        <ChatConsoleContent />
      </Suspense>
    </AppShell>
  );
}
