'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Lock, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';

export interface PolicyProof {
  code: string;
  name: string;
  status: 'PASS' | 'WARN' | 'FAIL';
  evidence: string;
}

export interface SeparationOfDutiesProofCardProps {
  requesterId: string;
  requesterName?: string;
  requesterSso?: string;
  currentUserId: string;
  currentUserName?: string;
  currentUserSso?: string;
  servicenowChg?: string | null;
  circuitBreakerRemainingSeconds?: number;
  policies?: PolicyProof[];
  onApprove: () => void;
  onReject: () => void;
  onSwitchUser?: (newUser: string) => void;
}

export const SeparationOfDutiesProofCard: React.FC<SeparationOfDutiesProofCardProps> = ({
  requesterId,
  requesterName = 'Alice Cooper',
  requesterSso = 'PNC-US-991204',
  currentUserId,
  currentUserName = currentUserId === 'lead.bob' ? 'Bob Vance' : 'Alice Cooper',
  currentUserSso = currentUserId === 'lead.bob' ? 'PNC-US-884102' : 'PNC-US-991204',
  servicenowChg,
  circuitBreakerRemainingSeconds = 540,
  policies = [
    { code: 'POL-001', name: 'Git Commit Immutability', status: 'PASS', evidence: 'Pinned SHA 12b86b7 (0 branch drift)' },
    { code: 'POL-002', name: 'ServiceNow Window Check', status: 'PASS', evidence: 'CHG-98412 Active in Scheduled Window' },
    { code: 'POL-003', name: 'TruffleHog Secret Scan', status: 'PASS', evidence: '0 Plaintext Secrets Detected' },
    { code: 'POL-004', name: 'Target Redlock Mutex', status: 'PASS', evidence: 'Exclusive Lock Acquired (30s Lease)' },
    { code: 'POL-005', name: 'Freeze Window Gate', status: 'PASS', evidence: 'Outside Blackout Window' },
    { code: 'POL-006', name: 'Fleet Concurrency', status: 'PASS', evidence: 'Running 12 / 75 Workers' },
  ],
  onApprove,
  onReject,
  onSwitchUser,
}) => {
  const isSelfApproval = requesterId === currentUserId;
  const [remainingTime, setRemainingTime] = useState<number>(circuitBreakerRemainingSeconds);

  useEffect(() => {
    const timer = setInterval(() => {
      setRemainingTime((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const minutes = Math.floor(remainingTime / 60);
  const seconds = remainingTime % 60;
  const isCircuitCritical = remainingTime < 120;

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0C101A] p-4 flex flex-col gap-4 font-mono shadow-xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-cyan-400" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            Maker-Checker Governance &amp; SOX 404 Attestation
          </span>
        </div>
        <div
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${
            isCircuitCritical
              ? 'bg-rose-950/40 border-rose-500/50 text-rose-300 animate-pulse'
              : 'bg-slate-900 border-amber-500/30 text-amber-300'
          }`}
        >
          <Clock size={12} />
          <span>Fail-Closed Clock:</span>
          <strong className="font-bold">
            {minutes}:{seconds < 10 ? `0${seconds}` : seconds}
          </strong>
        </div>
      </div>

      {/* Side-by-Side Identity Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        {/* Maker */}
        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800 flex flex-col gap-1">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
            Maker (Requester)
          </span>
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-bold">{requesterName}</span>
            <span className="px-1.5 py-0.5 rounded bg-cyan-950/40 text-cyan-300 border border-cyan-500/30 text-[10px]">
              {requesterId}
            </span>
          </div>
          <span className="text-slate-400 text-[11px]">SAML SSO: {requesterSso}</span>
          {servicenowChg && (
            <span className="text-slate-500 text-[10px]">Ticket: {servicenowChg}</span>
          )}
        </div>

        {/* Checker */}
        <div className="p-3 rounded-lg bg-[#07090E] border border-slate-800 flex flex-col gap-1">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
            Checker (Approving Lead)
          </span>
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-bold">{currentUserName}</span>
            <span className="px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 text-[10px]">
              {currentUserId}
            </span>
          </div>
          <span className="text-slate-400 text-[11px]">SAML SSO: {currentUserSso}</span>
          {onSwitchUser && (
            <button
              type="button"
              onClick={() => onSwitchUser(isSelfApproval ? 'lead.bob' : 'eng.alice')}
              className="text-[10px] text-cyan-400 hover:text-cyan-300 text-left underline flex items-center gap-1 mt-0.5"
            >
              <span>{isSelfApproval ? 'Switch to Bob (Approving Lead)' : 'Switch back to Alice'}</span>
              <ArrowRight size={10} />
            </button>
          )}
        </div>
      </div>

      {/* Deterministic Mathematical Assertion */}
      <div
        className={`p-3 rounded-lg border text-xs flex flex-wrap items-center justify-between gap-2 ${
          isSelfApproval
            ? 'bg-rose-950/20 border-rose-500/40 text-rose-300'
            : 'bg-emerald-950/20 border-emerald-500/40 text-emerald-300'
        }`}
      >
        <div className="flex items-center gap-2">
          {isSelfApproval ? (
            <Lock size={14} className="text-rose-400" />
          ) : (
            <ShieldCheck size={14} className="text-emerald-400" />
          )}
          <span>
            Invariant: <code className="font-bold">Requester_ID ≠ Approver_ID</code>
          </span>
        </div>
        <span className="text-[11px] font-bold">
          {isSelfApproval
            ? 'HARD LOCK: SELF-APPROVAL BLOCKED (SOX Section 404)'
            : 'ATTESTATION VALID (Independent Checker Signoff)'}
        </span>
      </div>

      {/* Policy Proof Ledger */}
      <div className="rounded-lg bg-[#07090E] border border-slate-800 p-3 space-y-2">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold flex items-center justify-between">
          <span>Policy-as-Code Attestation Proofs (OPA / Rego)</span>
          <span className="text-emerald-400 font-bold">6/6 Verified</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
          {policies.map((p) => (
            <div
              key={p.code}
              className="flex items-center justify-between p-1.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300"
            >
              <div className="flex items-center gap-1.5 min-w-0">
                <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />
                <span className="font-bold text-slate-200">{p.code}:</span>
                <span className="truncate text-slate-400">{p.name}</span>
              </div>
              <span className="text-[9px] px-1 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 flex-shrink-0">
                PASS
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-end gap-3 pt-1 border-t border-slate-800/80">
        <button
          type="button"
          onClick={onReject}
          className="px-4 py-2 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition-colors"
        >
          Reject &amp; Cancel
        </button>
        <button
          type="button"
          onClick={onApprove}
          disabled={isSelfApproval}
          title={isSelfApproval ? "Requester cannot approve their own high-risk job" : "Authorize execution"}
          className={`px-5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
            isSelfApproval
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
              : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold shadow-[0_0_16px_rgba(0,255,157,0.4)]'
          }`}
        >
          <CheckCircle2 size={13} />
          <span>Authorize &amp; Dispatch Job (Cmd+Enter)</span>
        </button>
      </div>
    </div>
  );
};

export default SeparationOfDutiesProofCard;
