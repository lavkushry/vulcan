'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import ChatAssistant, { ChatLaunchPayload } from '@/components/ChatAssistant';
import { TaskMonitor } from '@/components/TaskMonitor';
import { JobDetail } from '@/components/JobDetail';
import { ResizableDualPane } from '@/components/ResizableDualPane';
import { KeyboardShortcutsModal } from '@/components/KeyboardShortcutsModal';
import { useKeyboardHotkeys } from '@/hooks/useKeyboardHotkeys';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';
import type { Job, JobStatus } from '@/lib/types';
import { useRouter } from 'next/navigation';
import { Table2, ArrowRight, Keyboard } from 'lucide-react';

function ChatConsoleContent() {
  const { currentUser } = useVulcan();
  const router = useRouter();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'ALL'>('ALL');
  const [query, setQuery] = useState('');
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const refreshJobs = useCallback(async () => {
    try {
      const data = await api.listJobs();
      setJobs(data);
      // If no job selected, auto-select first or latest running
      if (!selectedId && data.length > 0) {
        setSelectedId(data[0].id);
      }
    } catch {
      /* ignore */
    }
  }, [selectedId]);

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
    if (selectedJob && selectedJob.status === 'PENDING_APPROVAL' && currentUser !== selectedJob.requester_id) {
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

      // Instantly refresh and select this new job so operator sees live terminal stream
      await refreshJobs();
      setSelectedId(created.id);
      return created;
    },
    [currentUser, refreshJobs]
  );

  // Left Pane component
  const leftPaneContent = (
    <div className="h-full flex flex-col bg-canvas-void">
      <div className="px-4 py-2 border-b border-glass-border flex items-center justify-between bg-glass-surface/40 select-none">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h1 className="text-xs font-mono font-semibold text-slate-200 uppercase tracking-wider">
            AI Chat Assistant · Natural Language Intent Resolution
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsHelpOpen(true)}
            className="text-[10px] font-mono text-slate-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
            title="Press '?' for hotkeys"
          >
            <Keyboard size={12} />
            <span>Hotkeys (?)</span>
          </button>
          <span className="text-[10px] font-mono text-slate-500">
            120+ Playbooks &amp; Stacks
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatAssistant
          currentUser={currentUser}
          onDispatchTask={handleDispatchTask}
          onSelectTaskToView={(corrId) => setSelectedId(corrId)}
        />
      </div>
    </div>
  );

  // Right Pane component
  const rightPaneContent = (
    <div className="h-full flex flex-col bg-glass-surface/30">
      <div className="px-4 py-2 border-b border-glass-border flex items-center justify-between bg-glass-surface/60 select-none">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
            Live Task Monitor &amp; Terminal
          </span>
          <span className="text-[10px] font-mono text-slate-500">
            (j/k to navigate, Cmd+Enter to approve)
          </span>
        </div>
        <button
          onClick={() => router.push('/matrix')}
          className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
        >
          <Table2 size={12} />
          <span>Full Task Matrix &amp; CSV</span>
          <ArrowRight size={10} />
        </button>
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
            onOpenFullMatrix={() => router.push('/matrix')}
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
      <ResizableDualPane
        leftPane={leftPaneContent}
        rightPane={rightPaneContent}
        defaultRatio={0.50}
        minRatio={0.25}
        maxRatio={0.75}
        storageKey="vulcan_chat_split_ratio"
      />

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
      <ChatConsoleContent />
    </AppShell>
  );
}
