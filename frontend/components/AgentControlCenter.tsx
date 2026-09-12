'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Play,
  FastForward,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  ShieldAlert,
  KeyRound,
  FileCode,
  Activity,
  Layers,
  Sparkles,
  RefreshCw,
  Search,
  ExternalLink,
  ChevronRight,
  Database,
  Terminal,
  Lock,
  ArrowRight,
  Check,
  AlertCircle,
  HelpCircle,
  BarChart3,
  Flame,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { AgentWorkflowContext, AgentWorkflowEvent, AgentVersionInfo, EvalRunRecord } from '@/lib/types';

export function AgentControlCenter() {
  const [activeTab, setActiveTab] = useState<'workflows' | 'agents' | 'evals'>('workflows');
  const [workflows, setWorkflows] = useState<AgentWorkflowContext[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState<AgentWorkflowContext | null>(null);
  const [events, setEvents] = useState<AgentWorkflowEvent[]>([]);
  const [agents, setAgents] = useState<AgentVersionInfo[]>([]);
  const [evalRuns, setEvalRuns] = useState<EvalRunRecord[]>([]);

  // Action states
  const [promptInput, setPromptInput] = useState(
    'Build and deploy a hardened PostgreSQL 16 production cluster on three RHEL 9 nodes with 500GB storage, Datadog monitoring, S3 backups, ServiceNow change control, and CyberArk credentials.'
  );
  const [environment, setEnvironment] = useState<'PROD' | 'STAGE' | 'DEV'>('PROD');
  const [requesterId, setRequesterId] = useState('eng.alice@bank.internal');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isStepping, setIsStepping] = useState(false);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const [isRunningEval, setIsRunningEval] = useState(false);
  const [evalTier, setEvalTier] = useState<number>(0);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Modals / Dialogs
  const [showResourceModal, setShowResourceModal] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showInputModal, setShowInputModal] = useState(false);
  const [approverId, setApproverId] = useState('lead.bob@bank.internal');
  const [approvalReason, setApprovalReason] = useState('Reviewed security architecture and change record CHG0091823.');
  const [operatorInputKey, setOperatorInputKey] = useState('');
  const [operatorInputValue, setOperatorInputValue] = useState('');

  // 1. Data Fetching
  const loadWorkflows = useCallback(async () => {
    try {
      const data = await api.listAgentWorkflows({ limit: 30 });
      setWorkflows(data);
      if (!selectedWorkflowId && data.length > 0) {
        setSelectedWorkflowId(data[0].workflow_id);
      }
    } catch {
      /* ignore */
    }
  }, [selectedWorkflowId]);

  const loadWorkflowDetails = useCallback(async (id: string) => {
    try {
      const [wf, ev] = await Promise.all([
        api.getAgentWorkflow(id),
        api.getAgentWorkflowEvents(id),
      ]);
      setSelectedWorkflow(wf);
      setEvents(ev);
    } catch {
      /* ignore */
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const ags = await api.listAgents();
      setAgents(ags);
    } catch {
      /* ignore */
    }
  }, []);

  const loadEvals = useCallback(async () => {
    try {
      const evs = await api.listEvals(20);
      setEvalRuns(evs);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadWorkflows();
    loadAgents();
    loadEvals();
    const interval = setInterval(() => {
      loadWorkflows();
      if (selectedWorkflowId) {
        loadWorkflowDetails(selectedWorkflowId);
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [loadWorkflows, loadAgents, loadEvals, selectedWorkflowId, loadWorkflowDetails]);

  useEffect(() => {
    if (selectedWorkflowId) {
      loadWorkflowDetails(selectedWorkflowId);
    }
  }, [selectedWorkflowId, loadWorkflowDetails]);

  // 2. Workflow Actions
  const handleCreateWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptInput.trim()) return;
    setIsSubmitting(true);
    setActionMessage(null);
    try {
      const newWf = await api.createAgentWorkflow({
        original_request: promptInput,
        requester_id: requesterId,
        environment,
      });
      setSelectedWorkflowId(newWf.workflow_id);
      setSelectedWorkflow(newWf);
      setActionMessage(`Workflow [${newWf.workflow_id}] created in RECEIVED state.`);
      await loadWorkflows();
    } catch (err: any) {
      setActionMessage(`Failed to create workflow: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStep = async () => {
    if (!selectedWorkflowId) return;
    setIsStepping(true);
    setActionMessage(null);
    try {
      const updated = await api.stepAgentWorkflow(selectedWorkflowId);
      setSelectedWorkflow(updated);
      await loadWorkflowDetails(selectedWorkflowId);
      await loadWorkflows();
      setActionMessage(`Stepped to [${updated.current_state}].`);
    } catch (err: any) {
      setActionMessage(`Step error: ${err.message}`);
    } finally {
      setIsStepping(false);
    }
  };

  const handleAutoRun = async () => {
    if (!selectedWorkflowId) return;
    setIsAutoRunning(true);
    setActionMessage(null);
    try {
      const res = await api.autoRunAgentWorkflow(selectedWorkflowId, 15);
      setSelectedWorkflow(res.workflow);
      await loadWorkflowDetails(selectedWorkflowId);
      await loadWorkflows();
      setActionMessage(
        `Auto-run finished: ${res.steps_taken} steps executed. State: [${res.workflow.current_state}].`
      );
    } catch (err: any) {
      setActionMessage(`Auto-run error: ${err.message}`);
    } finally {
      setIsAutoRunning(false);
    }
  };

  const handleResumeResource = async () => {
    if (!selectedWorkflowId) return;
    try {
      const updated = await api.resumeAgentWorkflow(selectedWorkflowId);
      setSelectedWorkflow(updated);
      setShowResourceModal(false);
      setActionMessage('Workflow resumed after resource configuration.');
      await loadWorkflowDetails(selectedWorkflowId);
    } catch (err: any) {
      setActionMessage(`Resume error: ${err.message}`);
    }
  };

  const handleApprove = async () => {
    if (!selectedWorkflowId) return;
    try {
      const updated = await api.approveAgentWorkflow(selectedWorkflowId, approverId, approvalReason);
      setSelectedWorkflow(updated);
      setShowApprovalModal(false);
      setActionMessage(`Approved by ${approverId}. State: [${updated.current_state}].`);
      await loadWorkflowDetails(selectedWorkflowId);
    } catch (err: any) {
      setActionMessage(`Approval error: ${err.message}`);
    }
  };

  const handleSupplyInput = async () => {
    if (!selectedWorkflowId || !operatorInputKey.trim()) return;
    try {
      const inputObj: Record<string, any> = { [operatorInputKey.trim()]: operatorInputValue.trim() };
      const updated = await api.supplyAgentWorkflowInput(selectedWorkflowId, inputObj);
      setSelectedWorkflow(updated);
      setShowInputModal(false);
      setOperatorInputKey('');
      setOperatorInputValue('');
      setActionMessage('Input supplied. Resuming automated workflow.');
      await loadWorkflowDetails(selectedWorkflowId);
    } catch (err: any) {
      setActionMessage(`Input submission error: ${err.message}`);
    }
  };

  const handleRollback = async () => {
    if (!selectedWorkflowId) return;
    try {
      const updated = await api.rollbackAgentWorkflow(selectedWorkflowId);
      setSelectedWorkflow(updated);
      setActionMessage('Rollback triggered successfully.');
      await loadWorkflowDetails(selectedWorkflowId);
    } catch (err: any) {
      setActionMessage(`Rollback error: ${err.message}`);
    }
  };

  const handleRunEval = async (tier: number) => {
    setIsRunningEval(true);
    setActionMessage(null);
    try {
      const res = await api.runEval(tier);
      setActionMessage(
        `Tier ${res.tier} Eval Completed: Pass Rate ${res.pass_rate_pct}% (95% CI: [${res.bootstrap_ci_95[0]}%, ${res.bootstrap_ci_95[1]}%]). Risk Score: ${res.risk_weighted_score}.`
      );
      await loadEvals();
    } catch (err: any) {
      setActionMessage(`Eval error: ${err.message}`);
    } finally {
      setIsRunningEval(false);
    }
  };

  // State Badge Coloring
  const getStateColor = (state: string) => {
    if (state === 'SUCCESS') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
    if (state.startsWith('WAITING_')) return 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse';
    if (state.includes('FAILED') || state.includes('DENIED') || state.includes('REJECTED'))
      return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
    if (state === 'EXECUTING') return 'bg-purple-500/20 text-purple-300 border-purple-500/40 animate-pulse';
    if (state === 'VERIFYING') return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40';
    if (state === 'EVALUATING') return 'bg-teal-500/20 text-teal-300 border-teal-500/40';
    return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
  };

  const canonicalSteps = [
    { label: 'Received', key: 'RECEIVED' },
    { label: 'Intent', key: 'UNDERSTANDING' },
    { label: 'Discovery', key: 'DISCOVERING' },
    { label: 'Planning', key: 'PLANNING' },
    { label: 'Composing', key: 'COMPOSING' },
    { label: 'Resources', key: 'RESOLVING_RESOURCES' },
    { label: 'Validation', key: 'VALIDATING' },
    { label: 'Security', key: 'SECURITY_REVIEW' },
    { label: 'Critic', key: 'CRITIC_REVIEW' },
    { label: 'Policy Gate', key: 'POLICY_CHECK' },
    { label: 'Approval', key: 'WAITING_FOR_APPROVAL' },
    { label: 'Ready', key: 'EXECUTION_READY' },
    { label: 'Execution', key: 'EXECUTING' },
    { label: 'Verification', key: 'VERIFYING' },
    { label: 'Success', key: 'SUCCESS' },
    { label: 'Eval', key: 'EVALUATING' },
  ];

  return (
    <div className="flex flex-col h-full bg-canvas-void text-slate-200">
      {/* ──── Header Bar ──── */}
      <div className="px-6 py-4 border-b border-glass-border bg-glass-surface/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Bot size={22} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide flex items-center gap-2 font-mono">
              AGENTOS ULTRA
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                Multi-Agent Operating System
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Deterministic Invariant: Agent Intelligence → Structured Proposal → Deterministic Governance → Constrained Execution → Independent Verification
            </p>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-lg border border-glass-border text-xs font-mono">
          <button
            onClick={() => setActiveTab('workflows')}
            className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
              activeTab === 'workflows' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Activity size={14} /> Live Workflows
          </button>
          <button
            onClick={() => setActiveTab('agents')}
            className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
              activeTab === 'agents' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Bot size={14} /> Specialists ({agents.length || 17})
          </button>
          <button
            onClick={() => setActiveTab('evals')}
            className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
              activeTab === 'evals' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-white'
            }`}
          >
            <BarChart3 size={14} /> Evals Platform
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div className="px-6 py-2 bg-cyan-950/60 border-b border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* ──── TAB 1: LIVE WORKFLOWS ──── */}
      {activeTab === 'workflows' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left Panel: Workflow List & Create Form */}
          <div className="w-96 border-r border-glass-border flex flex-col bg-canvas-base/50">
            {/* Create Form */}
            <div className="p-4 border-b border-glass-border bg-slate-900/40">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 font-mono flex items-center gap-2">
                <Sparkles size={13} className="text-cyan-400" />
                Dispatch Natural Language Goal
              </h2>
              <form onSubmit={handleCreateWorkflow} className="space-y-3">
                <textarea
                  rows={3}
                  value={promptInput}
                  onChange={(e) => setPromptInput(e.target.value)}
                  placeholder="Describe your infrastructure or operational goal..."
                  className="w-full text-xs font-mono bg-slate-950/80 border border-glass-border rounded p-2 text-slate-200 focus:border-cyan-400 focus:outline-none resize-none"
                />
                <div className="flex gap-2">
                  <select
                    value={environment}
                    onChange={(e) => setEnvironment(e.target.value as any)}
                    className="text-xs font-mono bg-slate-950 border border-glass-border rounded px-2 py-1 text-slate-300"
                  >
                    <option value="PROD">PROD</option>
                    <option value="STAGE">STAGE</option>
                    <option value="DEV">DEV</option>
                  </select>
                  <input
                    type="text"
                    value={requesterId}
                    onChange={(e) => setRequesterId(e.target.value)}
                    placeholder="Requester ID"
                    className="flex-1 text-xs font-mono bg-slate-950 border border-glass-border rounded px-2 py-1 text-slate-300"
                  />
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-mono font-medium disabled:opacity-50 flex items-center gap-1"
                  >
                    {isSubmitting ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                    Create
                  </button>
                </div>
              </form>
            </div>

            {/* Workflow List */}
            <div className="flex-1 overflow-y-auto divide-y divide-glass-border">
              <div className="p-2 px-4 text-xs font-mono text-slate-400 flex items-center justify-between bg-slate-900/30">
                <span>Active Workflows ({workflows.length})</span>
                <button onClick={loadWorkflows} className="hover:text-cyan-400">
                  <RefreshCw size={12} />
                </button>
              </div>
              {workflows.map((wf) => {
                const isSelected = wf.workflow_id === selectedWorkflowId;
                return (
                  <div
                    key={wf.workflow_id}
                    onClick={() => setSelectedWorkflowId(wf.workflow_id)}
                    className={`p-3 cursor-pointer transition-all ${
                      isSelected ? 'bg-cyan-950/30 border-l-2 border-cyan-400' : 'hover:bg-slate-900/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono font-semibold text-slate-200 truncate max-w-[170px]">
                        {wf.workflow_id}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${getStateColor(
                          wf.current_state
                        )}`}
                      >
                        {wf.current_state}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 line-clamp-2 mb-2 font-mono">
                      {wf.original_request}
                    </p>
                    <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono">
                      <span>Env: {wf.environment}</span>
                      <span>v{wf.version}</span>
                      <span>{new Date(wf.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                );
              })}
              {workflows.length === 0 && (
                <div className="p-8 text-center text-xs text-slate-500 font-mono">
                  No workflows active. Dispatch a requirement above to start.
                </div>
              )}
            </div>
          </div>

          {/* Right Panel: Selected Workflow Deep Inspector */}
          {selectedWorkflow ? (
            <div className="flex-1 flex flex-col overflow-y-auto bg-canvas-void p-6 space-y-6">
              {/* Header Info & Actions */}
              <div className="p-4 rounded-xl bg-slate-900/60 border border-glass-border flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-base font-bold font-mono text-white">{selectedWorkflow.workflow_id}</h2>
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full border font-mono font-semibold ${getStateColor(
                        selectedWorkflow.current_state
                      )}`}
                    >
                      {selectedWorkflow.current_state}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      Env: <strong className="text-white">{selectedWorkflow.environment}</strong>
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      Requester: <strong className="text-white">{selectedWorkflow.requester_id}</strong>
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 font-mono max-w-3xl bg-slate-950/60 p-2.5 rounded border border-glass-border">
                    {selectedWorkflow.original_request}
                  </p>
                </div>

                {/* Primary Action Buttons */}
                <div className="flex items-center gap-2 font-mono">
                  <button
                    onClick={handleStep}
                    disabled={isStepping || isAutoRunning}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-glass-border text-cyan-300 rounded text-xs font-medium flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {isStepping ? <RefreshCw size={13} className="animate-spin" /> : <ChevronRight size={14} />}
                    Step
                  </button>

                  <button
                    onClick={handleAutoRun}
                    disabled={isAutoRunning || isStepping}
                    className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-medium flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {isAutoRunning ? <RefreshCw size={13} className="animate-spin" /> : <FastForward size={14} />}
                    Auto-Run
                  </button>

                  {/* Pause Resolution Buttons */}
                  {selectedWorkflow.current_state === 'WAITING_FOR_RESOURCE' && (
                    <button
                      onClick={() => setShowResourceModal(true)}
                      className="px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded text-xs font-bold flex items-center gap-1.5 animate-bounce"
                    >
                      <AlertTriangle size={14} /> Resolve Missing Resource
                    </button>
                  )}

                  {selectedWorkflow.current_state === 'WAITING_FOR_APPROVAL' && (
                    <button
                      onClick={() => setShowApprovalModal(true)}
                      className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded text-xs font-bold flex items-center gap-1.5"
                    >
                      <ShieldCheck size={14} /> Maker-Checker Sign-off
                    </button>
                  )}

                  {selectedWorkflow.current_state === 'WAITING_FOR_INPUT' && (
                    <button
                      onClick={() => setShowInputModal(true)}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold flex items-center gap-1.5"
                    >
                      <HelpCircle size={14} /> Supply Input
                    </button>
                  )}

                  {(selectedWorkflow.current_state === 'VERIFY_FAILED' ||
                    selectedWorkflow.current_state === 'EXECUTION_FAILED') && (
                    <button
                      onClick={handleRollback}
                      className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-bold flex items-center gap-1.5"
                    >
                      <RotateCcw size={14} /> Trigger Rollback
                    </button>
                  )}
                </div>
              </div>

              {/* ──── Visual 16-Stage State Machine Timeline ──── */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border">
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                  <Clock size={13} className="text-cyan-400" />
                  Deterministic Lifecycle Pipeline
                </h3>
                <div className="grid grid-cols-8 gap-2">
                  {canonicalSteps.map((step, idx) => {
                    const isCurrent = selectedWorkflow.current_state === step.key;
                    const eventMatch = events.some((e) => e.to_state === step.key);
                    return (
                      <div
                        key={step.key}
                        className={`p-2 rounded-lg border text-center transition-all ${
                          isCurrent
                            ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 ring-1 ring-cyan-400/50'
                            : eventMatch
                            ? 'bg-slate-950/80 border-emerald-500/40 text-emerald-400'
                            : 'bg-slate-950/40 border-glass-border text-slate-500'
                        }`}
                      >
                        <div className="text-[10px] font-mono text-slate-500 mb-0.5">Stage {idx + 1}</div>
                        <div className="text-xs font-mono font-semibold truncate">{step.label}</div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* ──── Multi-Grid Specialist Evidence & Inspection Cards ──── */}
              <div className="grid grid-cols-2 gap-4 font-mono">
                {/* Intent & Discovery Card */}
                <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-300 font-bold border-b border-glass-border pb-1">
                    <span className="flex items-center gap-1.5">
                      <Search size={14} className="text-cyan-400" /> Intent & Catalog Discovery
                    </span>
                    <span className="text-[10px] text-cyan-400">
                      Domain: {selectedWorkflow.normalized_intent?.automation_domain || 'N/A'}
                    </span>
                  </div>
                  <div className="space-y-1 text-slate-400">
                    <div>
                      Target Platform:{' '}
                      <span className="text-white">
                        {selectedWorkflow.normalized_intent?.known_parameters?.os_platform || 'N/A'}
                      </span>
                    </div>
                    <div>
                      Nodes:{' '}
                      <span className="text-white">
                        {selectedWorkflow.normalized_intent?.known_parameters?.node_count || 'N/A'}
                      </span>
                    </div>
                    <div>
                      DB Version:{' '}
                      <span className="text-white">
                        {selectedWorkflow.normalized_intent?.known_parameters?.db_version || 'N/A'}
                      </span>
                    </div>
                    <div>
                      Storage:{' '}
                      <span className="text-white">
                        {selectedWorkflow.normalized_intent?.known_parameters?.storage_capacity || 'N/A'}
                      </span>
                    </div>
                    <div className="pt-1">
                      <span className="text-slate-500">Discovered Assets: </span>
                      <span className="text-cyan-300">
                        {selectedWorkflow.discovered_assets?.length ?? 0} candidates found
                      </span>
                    </div>
                  </div>
                </div>

                {/* Resource Dependencies & Zero Raw Secrets */}
                <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-300 font-bold border-b border-glass-border pb-1">
                    <span className="flex items-center gap-1.5">
                      <Database size={14} className="text-amber-400" /> External Resources & Secrets
                    </span>
                    <span className="text-[10px] text-emerald-400">Zero Raw Secrets Compliant</span>
                  </div>
                  <div className="space-y-1">
                    {selectedWorkflow.required_resources?.map((res, i) => (
                      <div key={i} className="flex items-center justify-between text-slate-400">
                        <span>{res.provider || res.resource_type}:</span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] ${
                            res.is_available ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300 font-bold'
                          }`}
                        >
                          {res.is_available ? 'CONNECTED' : 'MISSING'}
                        </span>
                      </div>
                    ))}
                    {(!selectedWorkflow.required_resources || selectedWorkflow.required_resources.length === 0) && (
                      <span className="text-slate-500">No resources evaluated yet.</span>
                    )}
                  </div>
                  {selectedWorkflow.secret_references?.length > 0 && (
                    <div className="pt-2 border-t border-glass-border">
                      <span className="text-[10px] text-slate-500">Secret Pointers:</span>
                      <div className="text-[10px] text-cyan-400 truncate">
                        {selectedWorkflow.secret_references.join(', ')}
                      </div>
                    </div>
                  )}
                </div>

                {/* Preflight Validation Factory & Adversarial Critic */}
                <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-300 font-bold border-b border-glass-border pb-1">
                    <span className="flex items-center gap-1.5">
                      <ShieldCheck size={14} className="text-purple-400" /> Validation Factory & Security
                    </span>
                    <span className="text-[10px] text-purple-400">
                      {selectedWorkflow.validation_results?.length || 0} Checks Run
                    </span>
                  </div>
                  <div className="space-y-1 text-slate-400">
                    {selectedWorkflow.validation_results?.map((val, idx) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span>{val.check_name}:</span>
                        <span className={val.passed ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                          {val.passed ? 'PASSED' : 'FAILED'}
                        </span>
                      </div>
                    ))}
                    <div>
                      Security Defects:{' '}
                      <span className="text-white font-bold">
                        {selectedWorkflow.security_findings?.length ?? 0}
                      </span>
                    </div>
                    <div>
                      Critic Counter-Arguments:{' '}
                      <span className="text-white font-bold">
                        {selectedWorkflow.critic_findings?.length ?? 0}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Independent Postcondition Verification Probes */}
                <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-300 font-bold border-b border-glass-border pb-1">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-400" /> Postcondition Probes
                    </span>
                    <span className="text-[10px] text-emerald-400">
                      {selectedWorkflow.postcondition_verification?.all_passed ? 'All Probes Passed' : 'Pending'}
                    </span>
                  </div>
                  <div className="space-y-1 text-slate-400">
                    {selectedWorkflow.postcondition_verification?.probes?.map((probe: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span>{probe.probe_id || probe.name}:</span>
                        <span className={probe.passed ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                          {probe.passed ? 'CONFIRMED' : 'FAILED'}
                        </span>
                      </div>
                    ))}
                    {(!selectedWorkflow.postcondition_verification?.probes ||
                      selectedWorkflow.postcondition_verification.probes.length === 0) && (
                      <span className="text-slate-500">Awaiting runner completion to execute independent probes.</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Cryptographic SHA-256 Merkle Audit Chain */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-glass-border">
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
                  <Lock size={13} className="text-cyan-400" />
                  Cryptographic Transition Audit Trail ({events.length} Events)
                </h3>
                <div className="max-h-48 overflow-y-auto divide-y divide-glass-border font-mono text-[11px]">
                  {events.map((ev) => (
                    <div key={ev.event_id} className="py-2 flex items-center justify-between text-slate-400">
                      <div className="flex items-center gap-2">
                        <span className="text-cyan-400 font-bold">{ev.from_state}</span>
                        <ArrowRight size={12} className="text-slate-500" />
                        <span className="text-emerald-400 font-bold">{ev.to_state}</span>
                        <span className="text-slate-500">[{ev.actor}]</span>
                        <span className="text-slate-400 truncate max-w-sm">{ev.reason}</span>
                      </div>
                      <div className="text-slate-600 text-[10px]">
                        Hash: {ev.event_hash.slice(0, 12)}...
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-500 font-mono text-xs">
              Select or create a workflow to inspect its state machine and agent actions.
            </div>
          )}
        </div>
      )}

      {/* ──── TAB 2: SPECIALISTS DIRECTORY ──── */}
      {activeTab === 'agents' && (
        <div className="flex-1 p-6 overflow-y-auto bg-canvas-void">
          <div className="max-w-6xl mx-auto space-y-4 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white">Registered Specialist Agents</h2>
                <p className="text-xs text-slate-400">
                  Specialized agents operating under narrow typed schemas, deterministic state transitions, and least privilege.
                </p>
              </div>
              <button
                onClick={loadAgents}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded text-xs border border-glass-border flex items-center gap-1.5"
              >
                <RefreshCw size={13} /> Refresh
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {agents.map((ag) => (
                <div key={ag.role} className="p-4 rounded-xl bg-slate-900/60 border border-glass-border space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-cyan-300 uppercase">{ag.role}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                      {ag.release_stage}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400">
                    Version: <span className="text-white">{ag.version}</span> | Model:{' '}
                    <span className="text-slate-300">{ag.model_name}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 bg-slate-950/60 p-2 rounded border border-glass-border line-clamp-3">
                    {ag.system_instructions}
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-glass-border">
                    <span>Benchmark: {ag.eval_benchmark_score}%</span>
                    <span>Invocations: {ag.total_invocations}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ──── TAB 3: EVALS BENCHMARK PLATFORM ──── */}
      {activeTab === 'evals' && (
        <div className="flex-1 p-6 overflow-y-auto bg-canvas-void">
          <div className="max-w-6xl mx-auto space-y-6 font-mono">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <BarChart3 size={18} className="text-teal-400" />
                  Multi-Tier Evaluation & Benchmark Engine
                </h2>
                <p className="text-xs text-slate-400">
                  Empirical quality evaluation across Tier 0 (PR Smoke) through Tier 7 (Self-Healing Chaos).
                </p>
              </div>

              {/* Trigger Benchmark Control */}
              <div className="flex items-center gap-2">
                <select
                  value={evalTier}
                  onChange={(e) => setEvalTier(Number(e.target.value))}
                  className="bg-slate-950 border border-glass-border rounded px-2.5 py-1 text-xs text-slate-200"
                >
                  <option value={0}>Tier 0: PR Smoke Gate</option>
                  <option value={1}>Tier 1: Feature Ground Truth</option>
                  <option value={2}>Tier 2: Boundary & Fuzz</option>
                  <option value={3}>Tier 3: Combinatorial Matrix</option>
                  <option value={4}>Tier 4: Enterprise Production</option>
                  <option value={5}>Tier 5: Adversarial Red-Team</option>
                  <option value={6}>Tier 6: Regression Delta</option>
                  <option value={7}>Tier 7: Self-Healing Chaos</option>
                </select>

                <button
                  onClick={() => handleRunEval(evalTier)}
                  disabled={isRunningEval}
                  className="px-3 py-1 bg-teal-600 hover:bg-teal-500 text-white rounded text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isRunningEval ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} />}
                  Run Tier {evalTier} Benchmark
                </button>
              </div>
            </div>

            {/* Eval Runs Table */}
            <div className="rounded-xl border border-glass-border bg-slate-900/40 overflow-hidden">
              <table className="w-full text-xs text-left">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-glass-border">
                  <tr>
                    <th className="p-3">Suite Name</th>
                    <th className="p-3">Tier</th>
                    <th className="p-3">Scenarios</th>
                    <th className="p-3">Pass Rate</th>
                    <th className="p-3">95% Bootstrap CI</th>
                    <th className="p-3">Risk-Weighted Score</th>
                    <th className="p-3">Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-glass-border">
                  {evalRuns.map((run, i) => (
                    <tr key={i} className="hover:bg-slate-900/30 text-slate-300">
                      <td className="p-3 font-semibold text-white">{run.suite_name}</td>
                      <td className="p-3">Tier {run.tier}</td>
                      <td className="p-3">
                        {run.passed_scenarios}/{run.total_scenarios} passed
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded font-bold ${
                            run.pass_rate_pct >= 90
                              ? 'bg-emerald-950 text-emerald-400'
                              : 'bg-amber-950 text-amber-400'
                          }`}
                        >
                          {run.pass_rate_pct}%
                        </span>
                      </td>
                      <td className="p-3 text-cyan-300">
                        [{run.bootstrap_ci_95[0]}%, {run.bootstrap_ci_95[1]}%]
                      </td>
                      <td className="p-3 font-bold text-purple-400">{run.risk_weighted_score}</td>
                      <td className="p-3 text-slate-500">{run.duration_ms}ms</td>
                    </tr>
                  ))}
                  {evalRuns.length === 0 && (
                    <tr>
                      <td colSpan={7} className="p-8 text-center text-slate-500">
                        No benchmark evaluations recorded yet. Run a tier evaluation above.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ──── MODAL 1: MISSING RESOURCE CONFIGURATION & 1-CLICK RESUME ──── */}
      {showResourceModal && selectedWorkflow && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-amber-500/40 rounded-xl p-6 max-w-lg w-full font-mono space-y-4 shadow-2xl">
            <div className="flex items-center justify-between text-amber-300 border-b border-glass-border pb-2">
              <span className="font-bold text-sm flex items-center gap-2">
                <AlertTriangle size={16} /> Resolve Missing External Resource
              </span>
              <button onClick={() => setShowResourceModal(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Workflow <strong>[{selectedWorkflow.workflow_id}]</strong> paused because external dependencies are
              unconfigured for environment <strong>[{selectedWorkflow.environment}]</strong>.
            </p>

            <div className="bg-slate-950 p-3 rounded border border-glass-border space-y-2 text-xs">
              <div className="text-slate-400">Missing Dependency Detected:</div>
              <div className="text-amber-300 font-bold text-sm">Datadog APM & Metrics / S3 Storage</div>
              <p className="text-slate-400 text-[11px]">
                Clicking resume will automatically verify credentials against the External Resources registry and
                continue execution without requiring re-prompting.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowResourceModal(false)}
                className="px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleResumeResource}
                className="px-4 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-1.5"
              >
                <Check size={14} /> Resume Workflow
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ──── MODAL 2: MAKER-CHECKER APPROVAL ──── */}
      {showApprovalModal && selectedWorkflow && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-purple-500/40 rounded-xl p-6 max-w-lg w-full font-mono space-y-4 shadow-2xl">
            <div className="flex items-center justify-between text-purple-300 border-b border-glass-border pb-2">
              <span className="font-bold text-sm flex items-center gap-2">
                <ShieldCheck size={16} /> Human Maker-Checker Sign-off
              </span>
              <button onClick={() => setShowApprovalModal(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              High-risk production deployment requires independent checker sign-off. Requester{' '}
              <strong className="text-rose-400">[{selectedWorkflow.requester_id}]</strong> cannot approve their own
              workflow.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Approver Identity (Checker):</label>
                <input
                  type="text"
                  value={approverId}
                  onChange={(e) => setApproverId(e.target.value)}
                  className="w-full bg-slate-950 border border-glass-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Approval Justification / Change Ticket:</label>
                <textarea
                  rows={2}
                  value={approvalReason}
                  onChange={(e) => setApprovalReason(e.target.value)}
                  className="w-full bg-slate-950 border border-glass-border rounded p-2 text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowApprovalModal(false)}
                className="px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                className="px-4 py-1.5 rounded bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-1.5"
              >
                <Check size={14} /> Authorize Execution
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ──── MODAL 3: OPERATOR INPUT SUPPLY ──── */}
      {showInputModal && selectedWorkflow && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-blue-500/40 rounded-xl p-6 max-w-lg w-full font-mono space-y-4 shadow-2xl">
            <div className="flex items-center justify-between text-blue-300 border-b border-glass-border pb-2">
              <span className="font-bold text-sm flex items-center gap-2">
                <HelpCircle size={16} /> Supply Missing Parameters
              </span>
              <button onClick={() => setShowInputModal(false)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              The Intent specialist detected ambiguous or missing parameters. Supply the required input to continue.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Parameter Key:</label>
                <input
                  type="text"
                  value={operatorInputKey}
                  onChange={(e) => setOperatorInputKey(e.target.value)}
                  placeholder="e.g. storage_capacity, db_version"
                  className="w-full bg-slate-950 border border-glass-border rounded p-2 text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Parameter Value:</label>
                <input
                  type="text"
                  value={operatorInputValue}
                  onChange={(e) => setOperatorInputValue(e.target.value)}
                  placeholder="e.g. 500GB, 16"
                  className="w-full bg-slate-950 border border-glass-border rounded p-2 text-white"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowInputModal(false)}
                className="px-3 py-1.5 rounded bg-slate-800 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                onClick={handleSupplyInput}
                className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs flex items-center gap-1.5"
              >
                <Check size={14} /> Submit & Resume
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
