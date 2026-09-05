'use client';

import React, { useState } from 'react';
import { ShieldAlert, CheckCircle, XCircle, AlertOctagon, UserCheck, Lock } from 'lucide-react';

interface MakerCheckerDeckProps {
  job: any;
  currentUserId?: string;
  onApprove: (decision: string, reason: string) => void;
  isProcessing?: boolean;
}

export default function MakerCheckerDeck({
  job,
  currentUserId = 'lead.bob',
  onApprove,
  isProcessing = false
}: MakerCheckerDeckProps) {
  const [reason, setReason] = useState('Reviewed architecture diff and verified ServiceNow maintenance schedule.');

  if (!job || job.status !== 'PENDING_APPROVAL') {
    return null;
  }

  const isSelfApproval = currentUserId === job.requester_id;

  return (
    <div className="glass-panel border border-amber-500/30 rounded-xl p-5 shadow-glow-amber space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-amber-500/20 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
              MAKER-CHECKER AUTHORIZATION DECK
              <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono">
                PNC BANK SEPARATION OF DUTIES
              </span>
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Job: {job.correlation_id} • Target: {job.target_resource_id} • Tier: {job.risk_tier}
            </p>
          </div>
        </div>

        <div className="text-right font-mono text-xs">
          <div className="text-amber-400 font-bold">15-MIN TIMEOUT GATE</div>
          <div className="text-slate-400">Fail-Closed Enforcement</div>
        </div>
      </div>

      {/* Identity & Invariant Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
        <div className="bg-glass-raised p-3 rounded border border-glass-border">
          <div className="text-slate-400 text-[10px] uppercase">Maker (Requester)</div>
          <div className="text-white font-bold mt-1">{job.requester_id}</div>
          <div className="text-[11px] text-slate-500 mt-1">Submitted at: {new Date(job.created_at).toLocaleTimeString()}</div>
        </div>

        <div className="bg-glass-raised p-3 rounded border border-glass-border">
          <div className="text-slate-400 text-[10px] uppercase">Active Checker (Viewer)</div>
          <div className="text-cyan-400 font-bold mt-1">{currentUserId}</div>
          <div className="text-[11px] text-slate-400 mt-1">
            {isSelfApproval ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <AlertOctagon className="w-3.5 h-3.5" />
                SELF-APPROVAL DETECTED (LOCKED)
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1">
                <UserCheck className="w-3.5 h-3.5" />
                Authorized Checker Identity Valid
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Structured Payload Diff */}
      <div className="bg-canvas-subtle p-3 rounded border border-glass-border text-xs font-mono space-y-1">
        <div className="text-slate-400 text-[10px] uppercase">Structured Change Manifest</div>
        <div className="text-slate-300">Playbook: <span className="text-cyan-400">{job.playbook_identifier}</span></div>
        <div className="text-slate-300">ServiceNow CHG: <span className="text-emerald-400">{job.servicenow_chg}</span></div>
        <div className="text-slate-300">Parameters:</div>
        <pre className="text-xs text-amber-300/90 bg-black/40 p-2 rounded overflow-x-auto">
          {JSON.stringify(job.parameters, null, 2)}
        </pre>
      </div>

      {/* Decision Input */}
      <div className="space-y-2">
        <label className="text-[10px] font-mono uppercase text-slate-400">Checker Sign-off Work Notes</label>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for approval or rejection..."
          className="w-full bg-glass-raised border border-glass-border rounded px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-400"
        />
      </div>

      {/* Anti-Self-Approval Action Buttons */}
      <div className="flex items-center justify-between pt-2">
        {isSelfApproval ? (
          <div className="text-xs text-rose-400 font-mono flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Banking Rule: You cannot approve your own change. An independent Checker must sign off.
          </div>
        ) : (
          <div className="text-xs text-emerald-400 font-mono flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            Distinct Checker verified. Cryptographic audit sign-off enabled.
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onApprove('REJECT', reason)}
            disabled={isProcessing}
            className="px-4 py-2 rounded bg-rose-950/50 hover:bg-rose-900 border border-rose-500/40 text-rose-300 font-mono text-xs font-bold transition-all disabled:opacity-50 flex items-center gap-1.5"
          >
            <XCircle className="w-4 h-4" />
            DENY REQUEST
          </button>

          <button
            type="button"
            onClick={() => onApprove('APPROVE', reason)}
            disabled={isProcessing || isSelfApproval}
            className="px-5 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-bold shadow-glow-emerald transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            <CheckCircle className="w-4 h-4" />
            {isProcessing ? 'COMMITTING AUDIT...' : 'SIGN & AUTHORIZE [ENTER]'}
          </button>
        </div>
      </div>
    </div>
  );
}
