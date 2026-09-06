"use client";
import { useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { TaskMonitor } from "@/components/TaskMonitor";
import { JobDetail } from "@/components/JobDetail";
import { useJobs } from "@/hooks/useJobs";
import { DEMO_USERS } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function Home() {
  const [currentUser, setCurrentUser] = useState(DEMO_USERS[0].id);
  const { jobs, filtered, statusFilter, setStatusFilter, query, setQuery, refresh } = useJobs();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = jobs.find((j) => j.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col bg-[#07090E] text-slate-100">
      <header className="flex items-center gap-4 border-b border-slate-800/80 bg-[#0A0E16] px-5 py-3">
        <span className="font-mono text-sm font-bold tracking-widest text-cyan-400">VULCAN</span>
        <span className="text-xs text-slate-500">Enterprise Automation Control Plane — Operator Console</span>
        <label className="ml-auto flex items-center gap-2 text-xs text-slate-400">
          acting as
          <select value={currentUser} onChange={(e) => setCurrentUser(e.target.value)}
            className="rounded-md border border-slate-700 bg-[#07090E] px-2 py-1 text-xs text-slate-200">
            {DEMO_USERS.map((u) => <option key={u.id} value={u.id}>{u.label}</option>)}
          </select>
        </label>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden min-h-0 w-[380px] shrink-0 md:flex">
          <ChatPanel currentUser={currentUser}
            onJobCreated={(job: Job) => { refresh(); setSelectedId(job.id); }} />
        </div>
        <TaskMonitor jobs={filtered} allJobs={jobs} selectedId={selectedId} onSelect={setSelectedId}
          statusFilter={statusFilter} setStatusFilter={setStatusFilter} query={query} setQuery={setQuery} />
        <JobDetail job={selected} currentUser={currentUser} onChanged={refresh} />
      </div>
    </div>
  );
}
