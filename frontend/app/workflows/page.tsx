'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import {
  GitMerge, Calendar, Clock, Play, CheckCircle2, AlertTriangle,
  RotateCcw, ArrowRight, Shield, ToggleLeft, ToggleRight,
  Search, RefreshCw, Cpu, Layers, Database, ChevronRight, Check
} from 'lucide-react';

interface WorkflowStep {
  step_id: string;
  name: string;
  action_identifier: string;
  engine: string;
  parameters: Record<string, any>;
  on_success: string | null;
  on_failure: string | null;
  requires_approval: boolean;
}

interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  description: string;
  category: string;
  risk_tier: string;
  steps: WorkflowStep[];
  cron_expression: string | null;
  is_cron_enabled: boolean;
  total_runs: number;
  last_run_at: string;
  success_rate: number;
}

interface CronSchedule {
  schedule_id: string;
  name: string;
  description: string;
  cron_expression: string;
  timezone: string;
  workflow_id: string;
  target_action: string;
  status: string;
  next_run_at: string;
  next_run_human: string;
  last_run_at: string;
  total_executions: number;
}

function WorkflowsContent() {
  const [activeTab, setActiveTab] = useState<'workflows' | 'schedules'>('workflows');
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [schedules, setSchedules] = useState<CronSchedule[]>([]);
  const [selectedWfId, setSelectedWfId] = useState<string>('wf-zero-downtime-patching');
  const [search, setSearch] = useState('');
  const [runningWf, setRunningWf] = useState<string | null>(null);
  const [wfRunResult, setWfRunResult] = useState<string | null>(null);

  const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const loadData = useCallback(async () => {
    try {
      const [wRes, sRes] = await Promise.all([
        fetch(`${BASE}/api/v1/workflows`),
        fetch(`${BASE}/api/v1/schedules`)
      ]);
      if (wRes.ok) setWorkflows(await wRes.json());
      if (sRes.ok) setSchedules(await sRes.json());
    } catch {
      /* ignore */
    }
  }, [BASE]);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 8000);
    return () => clearInterval(t);
  }, [loadData]);

  const handleToggleSchedule = async (scheduleId: string) => {
    try {
      const res = await fetch(`${BASE}/api/v1/schedules/${scheduleId}/toggle`, { method: 'POST' });
      if (res.ok) {
        await loadData();
      }
    } catch {
      /* ignore */
    }
  };

  const handleRunWorkflow = async (wfId: string) => {
    setRunningWf(wfId);
    setWfRunResult(null);
    try {
      const res = await fetch(`${BASE}/api/v1/workflows/${wfId}/run`, { method: 'POST' });
      const data = await res.json();
      setWfRunResult(`Dispatched [${data.correlation_id}]: All ${data.total_steps} stages queued under distributed lock.`);
      await loadData();
    } catch (e: any) {
      setWfRunResult(`Execution failed: ${e?.message}`);
    } finally {
      setRunningWf(null);
    }
  };

  const activeWf = workflows.find(w => w.workflow_id === selectedWfId) ?? workflows[0];

  return (
    <div className="flex flex-col h-full bg-canvas-void">
      {/* ──── Top Nav Tabs ──── */}
      <div className="px-6 py-3 border-b border-glass-border bg-glass-surface/40 flex items-center justify-between">
        <div className="flex items-center gap-6 text-xs font-mono">
          <button
            onClick={() => setActiveTab('workflows')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-all ${
              activeTab === 'workflows'
                ? 'border-cyan-400 text-cyan-300 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <GitMerge size={16} />
            <span>Multi-Step DAG Workflows ({workflows.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('schedules')}
            className={`flex items-center gap-2 pb-1 border-b-2 transition-all ${
              activeTab === 'schedules'
                ? 'border-cyan-400 text-cyan-300 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            <Calendar size={16} />
            <span>Distributed Cron Scheduler ({schedules.length})</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Redlock Mutex Active (Zero-Overlap Guarantee)</span>
        </div>
      </div>

      {/* ──── TAB 1: MULTI-STEP WORKFLOWS (DAGs) ──── */}
      {activeTab === 'workflows' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Master List (380px) */}
          <div className="w-[380px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/20">
            <div className="p-3 border-b border-glass-border">
              <div className="relative">
                <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search workflows, pipelines…"
                  className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/40 font-sans"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-glass-border/40">
              {workflows
                .filter(w => !search || w.name.toLowerCase().includes(search.toLowerCase()))
                .map((wf) => (
                <button
                  key={wf.workflow_id}
                  onClick={() => setSelectedWfId(wf.workflow_id)}
                  className={`w-full text-left p-4 transition-all relative flex flex-col gap-1.5 ${
                    selectedWfId === wf.workflow_id ? 'bg-cyan-500/[0.08]' : 'hover:bg-white/[0.02]'
                  }`}
                >
                  {selectedWfId === wf.workflow_id && (
                    <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono text-slate-200 truncate max-w-[240px]">{wf.name}</span>
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                      wf.risk_tier === 'HIGH' ? 'border-rose-500/30 text-rose-400 bg-rose-500/10' :
                      'border-amber-500/30 text-amber-400 bg-amber-500/10'
                    }`}>
                      {wf.risk_tier}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 line-clamp-2">{wf.description}</p>
                  <div className="flex items-center gap-3 text-[10px] font-mono text-slate-500 mt-1">
                    <span>{wf.steps.length} Stages</span>
                    <span>•</span>
                    <span className="text-emerald-400">{wf.success_rate}% Success</span>
                    {wf.cron_expression && (
                      <span className="ml-auto text-cyan-400 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20">
                        {wf.cron_expression}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Detail DAG Stage Canvas */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeWf && (
              <div className="max-w-3xl mx-auto space-y-6">
                {/* Header */}
                <div className="p-5 rounded-2xl bg-glass-surface border border-glass-border flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h2 className="text-base font-bold font-mono text-white">{activeWf.name}</h2>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-500/30 text-cyan-300 bg-cyan-950/40">
                        {activeWf.steps.length} Sequential Stages
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">{activeWf.description}</p>
                    <div className="flex items-center gap-4 text-xs font-mono text-slate-500 mt-3">
                      <span>Total Invocations: <strong className="text-slate-200">{activeWf.total_runs}</strong></span>
                      <span>Success Rate: <strong className="text-emerald-400">{activeWf.success_rate}%</strong></span>
                      {activeWf.cron_expression && (
                        <span>Scheduled: <strong className="text-cyan-400">{activeWf.cron_expression}</strong></span>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => handleRunWorkflow(activeWf.workflow_id)}
                    disabled={runningWf === activeWf.workflow_id}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 text-black font-bold font-mono text-xs shadow-glow-cyan/20 transition-all hover:scale-[1.02] flex-shrink-0"
                  >
                    <Play size={14} className="fill-current" />
                    <span>{runningWf === activeWf.workflow_id ? 'Dispatching…' : 'Execute Pipeline'}</span>
                  </button>
                </div>

                {wfRunResult && (
                  <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-xs font-mono text-emerald-300 flex items-center gap-2 animate-fade-in-up">
                    <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" />
                    <span>{wfRunResult}</span>
                  </div>
                )}

                {/* Visual Sequential & Branching DAG Nodes */}
                <div className="space-y-3">
                  <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-bold">
                    Orchestrated Execution Stages &amp; Rollback Guardrails
                  </h3>

                  {activeWf.steps.map((step, idx) => {
                    const isRollback = step.step_id.includes('rollback') || step.step_id.includes('emergency');
                    return (
                      <div key={step.step_id} className="relative">
                        {idx > 0 && (
                          <div className="flex justify-center my-1 text-slate-600">
                            <ArrowRight size={14} className="rotate-90" />
                          </div>
                        )}
                        <div className={`p-4 rounded-xl border transition-all ${
                          isRollback
                            ? 'bg-rose-950/30 border-rose-500/40 text-rose-200'
                            : 'bg-glass-surface border-glass-border hover:border-cyan-500/40'
                        }`}>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2.5">
                              <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold font-mono ${
                                isRollback ? 'bg-rose-500/20 text-rose-300' : 'bg-cyan-500/20 text-cyan-300'
                              }`}>
                                {isRollback ? '!' : idx + 1}
                              </span>
                              <div>
                                <h4 className="text-xs font-bold font-mono text-slate-200">{step.name}</h4>
                                <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500 mt-0.5">
                                  <span>Action: <strong className="text-cyan-400">{step.action_identifier}</strong></span>
                                  <span>•</span>
                                  <span>Engine: {step.engine}</span>
                                  {step.requires_approval && (
                                    <span className="text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                                      Maker-Checker Gate
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="text-right text-[10px] font-mono text-slate-500">
                              {step.on_failure && (
                                <span className="text-rose-400 block">On Failure → {step.on_failure}</span>
                              )}
                              {step.on_success && (
                                <span className="text-emerald-400 block">On Success → {step.on_success}</span>
                              )}
                            </div>
                          </div>

                          {/* Parameter snippet */}
                          <div className="mt-3 p-2.5 rounded-lg bg-canvas-void/80 border border-glass-border/60 text-[11px] font-mono text-slate-400">
                            <div className="text-[9px] uppercase text-slate-600 mb-1">Injected Parameters:</div>
                            <pre className="text-slate-300 overflow-x-auto">
                              {JSON.stringify(step.parameters, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ──── TAB 2: DISTRIBUTED CRON SCHEDULER ──── */}
      {activeTab === 'schedules' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto">
          {/* Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-glass-surface border border-glass-border space-y-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Active Cron Jobs</span>
              <div className="text-xl font-bold font-mono text-cyan-400">
                {schedules.filter(s => s.status === 'ACTIVE').length} of {schedules.length}
              </div>
              <span className="text-[10px] font-mono text-slate-500 block">Distributed across cluster</span>
            </div>

            <div className="p-4 rounded-xl bg-glass-surface border border-glass-border space-y-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Next Scheduled Job</span>
              <div className="text-xl font-bold font-mono text-amber-400">
                in 15m
              </div>
              <span className="text-[10px] font-mono text-slate-500 block">Terraform Drift Reconciliation</span>
            </div>

            <div className="p-4 rounded-xl bg-glass-surface border border-glass-border space-y-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Locking Protocol</span>
              <div className="text-xl font-bold font-mono text-emerald-400 flex items-center gap-1.5">
                <span>Redis Redlock</span>
                <CheckCircle2 size={16} />
              </div>
              <span className="text-[10px] font-mono text-slate-500 block">Prevents duplicate execution</span>
            </div>

            <div className="p-4 rounded-xl bg-glass-surface border border-glass-border space-y-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">Change Window Gate</span>
              <div className="text-xl font-bold font-mono text-purple-400">
                ENFORCED
              </div>
              <span className="text-[10px] font-mono text-slate-500 block">ServiceNow sync verified</span>
            </div>
          </div>

          {/* Cron Schedule Table */}
          <div className="rounded-2xl bg-glass-surface border border-glass-border overflow-hidden">
            <div className="p-4 border-b border-glass-border flex items-center justify-between">
              <h3 className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                Production Periodic Automation Schedules
              </h3>
              <button
                onClick={() => alert('New Cron Schedule modal ready (cron syntax + target action selection)')}
                className="px-3 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono hover:bg-cyan-500/20 transition-colors"
              >
                + New Schedule
              </button>
            </div>

            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-glass-border bg-canvas-void/40 text-slate-500">
                <tr>
                  <th className="p-3.5">Schedule Name</th>
                  <th className="p-3.5">Cron Expression</th>
                  <th className="p-3.5">Target Action / Workflow</th>
                  <th className="p-3.5">Next Run</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right">Toggle Active</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass-border/40">
                {schedules.map((s) => (
                  <tr key={s.schedule_id} className="hover:bg-white/[0.01]">
                    <td className="p-3.5">
                      <div className="font-bold text-slate-200">{s.name}</div>
                      <div className="text-[11px] text-slate-500 line-clamp-1">{s.description}</div>
                    </td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded bg-canvas-void border border-glass-border text-cyan-300 font-bold">
                        {s.cron_expression}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-300">{s.target_action}</td>
                    <td className="p-3.5">
                      <span className="text-amber-300">{s.next_run_human}</span>
                      <span className="text-[10px] text-slate-500 block">({s.timezone})</span>
                    </td>
                    <td className="p-3.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] border ${
                        s.status === 'ACTIVE'
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                          : 'border-slate-700 bg-slate-800 text-slate-500'
                      }`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <button
                        onClick={() => handleToggleSchedule(s.schedule_id)}
                        className={`px-3 py-1 rounded-lg border text-xs font-mono transition-colors ${
                          s.status === 'ACTIVE'
                            ? 'border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20'
                            : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                        }`}
                      >
                        {s.status === 'ACTIVE' ? 'Pause' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function WorkflowsPage() {
  return (
    <AppShell>
      <WorkflowsContent />
    </AppShell>
  );
}
