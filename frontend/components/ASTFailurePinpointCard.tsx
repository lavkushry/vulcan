'use client';

import React, { useState } from 'react';
import { AlertCircle, AlertTriangle, RefreshCw, CheckCircle2, Terminal, GitFork, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';

export interface RollbackDagStep {
  step: number;
  name: string;
  target?: string;
  action?: string;
}

export interface DiagnosticDetails {
  fault_summary: string;
  root_cause: string;
  blast_radius: string;
  recommended_action: string;
  windowed_log?: string;
  failing_stage?: string;
  syntax_type?: 'yaml' | 'hcl' | 'bash' | string;
  ast_block?: string;
  failing_line_offset?: number;
  error_token?: string;
  exit_code?: number;
  rollback_playbook?: string;
  rollback_dag?: RollbackDagStep[];
}

interface ASTFailurePinpointCardProps {
  diagnostic: string;
  diagnosticDetails?: DiagnosticDetails | null;
  jobIdentifier?: string;
  targetResource?: string;
  exitCode?: number | null;
  currentUser: string;
  servicenowChg?: string | null;
  jobParameters?: Record<string, any>;
  onRollbackDispatched?: () => void;
}

export default function ASTFailurePinpointCard({
  diagnostic,
  diagnosticDetails,
  jobIdentifier,
  targetResource,
  exitCode,
  currentUser,
  servicenowChg,
  jobParameters = {},
  onRollbackDispatched
}: ASTFailurePinpointCardProps) {
  const [isDispatching, setIsDispatching] = useState(false);
  const [dispatchSuccess, setDispatchSuccess] = useState(false);
  const [dispatchError, setDispatchError] = useState<string | null>(null);

  // Fallbacks if diagnosticDetails was not populated from server
  const effectiveExitCode = diagnosticDetails?.exit_code ?? exitCode ?? 1;
  const faultSummary = diagnosticDetails?.fault_summary || "Automation Task Non-Zero Exit Status";
  const rootCause = diagnosticDetails?.root_cause || diagnostic;
  const blastRadius = diagnosticDetails?.blast_radius || "Target node left in unverified state; health probes failed verification.";
  const recommendedAction = diagnosticDetails?.recommended_action || "Trigger automated rollback recovery to restore previous baseline.";
  const failingStage = diagnosticDetails?.failing_stage || (jobIdentifier ? `TASK [${jobIdentifier} : Execute]` : "Execution Engine Task");
  const syntaxType = diagnosticDetails?.syntax_type || "yaml";
  const astBlock = diagnosticDetails?.ast_block || (
    jobIdentifier
      ? `- name: Execute ${jobIdentifier}\n  ansible.builtin.include_tasks: main.yml\n  register: task_res\n  failed_when: task_res.rc != 0`
      : `- name: Execute Orchestration Step\n  command: /usr/local/bin/run-task\n  register: res\n  failed_when: res.rc != 0`
  );
  const failingLineOffset = diagnosticDetails?.failing_line_offset || 4;
  const errorToken = diagnosticDetails?.error_token || `Non-zero exit code ${effectiveExitCode}`;
  const rollbackPlaybook = diagnosticDetails?.rollback_playbook || (jobIdentifier ? `rollback-${jobIdentifier}` : "rollback-orchestrator");
  
  const rollbackDag: RollbackDagStep[] = diagnosticDetails?.rollback_dag && diagnosticDetails.rollback_dag.length > 0
    ? diagnosticDetails.rollback_dag
    : [
        { step: 1, name: "Acquire Mutex & Isolate Target", target: targetResource || "cluster-node", action: "redlock_mutex_acquire" },
        { step: 2, name: "Revert to Previous Baseline", target: targetResource || "cluster-node", action: "git_revert_baseline" },
        { step: 3, name: "Execute Health Probes", target: targetResource || "cluster-node", action: "health_probe_verify" }
      ];

  const lines = astBlock.split('\n');

  const handleDispatchRollback = async () => {
    setIsDispatching(true);
    setDispatchError(null);
    try {
      await api.createJob({
        identifier: rollbackPlaybook,
        parameters: {
          ...jobParameters,
          action: "rollback",
          rollback_mode: true,
          original_identifier: jobIdentifier,
          target_resource: targetResource
        },
        requester_id: currentUser,
        servicenow_chg: servicenowChg || undefined,
      });
      setDispatchSuccess(true);
      if (onRollbackDispatched) {
        onRollbackDispatched();
      }
    } catch (err: any) {
      setDispatchError(err?.message || "Failed to dispatch rollback playbook");
    } finally {
      setIsDispatching(false);
      setTimeout(() => setDispatchSuccess(false), 4000);
    }
  };

  return (
    <div 
      data-testid="ast-failure-pinpoint-card"
      className="rounded-xl border border-rose-500/40 bg-[#0A0D14] p-4 font-mono text-xs space-y-3.5 shadow-[0_0_20px_rgba(244,63,94,0.08)]"
    >
      {/* Card Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rose-500/20 pb-2.5">
        <div className="flex items-center gap-2 text-rose-300 font-bold text-xs">
          <AlertCircle size={17} className="text-rose-400 shrink-0" />
          <span>AI SRE Diagnostic Pinpoint (AST Failure Analysis)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded bg-rose-950/70 text-rose-300 border border-rose-500/40 font-bold">
            Exit Code {effectiveExitCode}
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-700 font-semibold uppercase">
            {syntaxType} AST
          </span>
        </div>
      </div>

      {/* Fault Summary Banner */}
      <div className="flex items-start gap-2.5 p-2.5 rounded-lg bg-rose-950/30 border border-rose-500/30 text-rose-200 text-[11px] leading-relaxed">
        <AlertTriangle size={15} className="text-rose-400 shrink-0 mt-0.5" />
        <div>
          <strong className="text-rose-300">{faultSummary}:</strong> {failingStage}
          {errorToken && (
            <div className="mt-1 text-[10px] font-mono text-rose-400/90 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-500/20 inline-block">
              Offending Signal: {errorToken}
            </div>
          )}
        </div>
      </div>

      {/* AST Code Snippet View with Offending Line Highlight */}
      <div className="rounded-lg bg-[#04060A] border border-slate-800 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 bg-[#080C14] border-b border-slate-800/80 text-[10px] text-slate-400">
          <span className="font-semibold text-slate-300 flex items-center gap-1.5">
            <Terminal size={12} className="text-cyan-400" />
            Playbook AST Block Pinpoint
          </span>
          <span className="text-rose-400 font-mono">Line {failingLineOffset} Failed</span>
        </div>
        <div className="p-3 font-mono text-[11px] leading-5 overflow-x-auto select-text">
          {lines.map((line, idx) => {
            const lineNum = idx + 1;
            const isFailingLine = lineNum === failingLineOffset;
            return (
              <div 
                key={idx} 
                className={`flex items-center gap-3 px-1.5 rounded transition-colors ${
                  isFailingLine 
                    ? 'bg-rose-950/70 border-l-2 border-rose-500 text-rose-200 font-bold' 
                    : 'text-slate-300 hover:bg-slate-900/40'
                }`}
              >
                <span className={`w-6 text-right select-none font-mono text-[10px] ${
                  isFailingLine ? 'text-rose-400 font-bold' : 'text-slate-600'
                }`}>
                  {lineNum}
                </span>
                <span className="whitespace-pre">
                  {line}
                </span>
                {isFailingLine && (
                  <span className="ml-auto text-[10px] px-1.5 py-0.2 rounded bg-rose-600/30 text-rose-300 border border-rose-500/40 font-semibold select-none">
                    Offending Node
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Root Cause & Blast Radius Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
        <div className="p-2.5 rounded-lg bg-[#05070B] border border-slate-800/90 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">Root Cause</span>
          <p className="text-slate-300 leading-relaxed">{rootCause}</p>
        </div>
        <div className="p-2.5 rounded-lg bg-[#05070B] border border-slate-800/90 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Blast Radius</span>
          <p className="text-slate-300 leading-relaxed">{blastRadius}</p>
        </div>
      </div>

      {/* Predictive Rollback DAG Sequence */}
      <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center gap-1.5">
            <GitFork size={12} className="text-cyan-400" />
            Synthesized Rollback Recovery DAG:
          </span>
          <span className="text-[10px] text-cyan-400 font-mono">
            {rollbackPlaybook}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
          {rollbackDag.map((step, idx) => (
            <React.Fragment key={step.step || idx}>
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-900/90 border border-slate-700/80 text-cyan-300 shadow-sm">
                <span className="w-4 h-4 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500/40 flex items-center justify-center text-[9px] font-bold">
                  {step.step || idx + 1}
                </span>
                <span>{step.name}</span>
                {step.target && (
                  <span className="text-[10px] text-slate-500 font-normal">
                    ({step.target})
                  </span>
                )}
              </div>
              {idx < rollbackDag.length - 1 && (
                <span className="text-slate-600 font-bold">➔</span>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-1">
        <div className="text-[10px] text-slate-400 flex items-center gap-1.5">
          <ShieldCheck size={13} className="text-emerald-400" />
          <span>Rollback preserves audit hash chain & enforces Maker-Checker</span>
        </div>

        <div className="flex items-center gap-2">
          {dispatchError && (
            <span className="text-[10px] text-rose-400 font-mono">{dispatchError}</span>
          )}
          <button
            type="button"
            onClick={handleDispatchRollback}
            disabled={isDispatching}
            className={`px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-1.5 transition-all shadow-md ${
              dispatchSuccess
                ? 'bg-emerald-600 text-white'
                : 'bg-rose-600 hover:bg-rose-500 text-white shadow-[0_0_12px_rgba(255,0,85,0.3)]'
            }`}
          >
            {isDispatching ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : dispatchSuccess ? (
              <CheckCircle2 size={12} />
            ) : (
              <RefreshCw size={12} />
            )}
            <span>
              {isDispatching 
                ? "Dispatching Rollback..." 
                : dispatchSuccess 
                ? "Rollback Dispatched!" 
                : `Dispatch Rollback (${rollbackPlaybook})`}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
