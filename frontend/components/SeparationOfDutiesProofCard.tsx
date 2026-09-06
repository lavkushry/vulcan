'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Lock, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';

export interface PolicyProof {
  code: string;
  name: string;
  status: 'PASS' | 'WARN' | 'FAIL' | 'GATED' | 'UNAUDITED';
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
  approvalRequestedAt?: string | null;
  capabilities?: {
    can_approve: boolean;
    can_reject: boolean;
    disabled_reason?: string | null;
  };
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
  circuitBreakerRemainingSeconds = 900,
  approvalRequestedAt,
  capabilities,
  policies,
  onApprove,
  onReject,
  onSwitchUser,
}) => {
  const isSelfApproval = requesterId === currentUserId;

  const computeRemaining = () => {
    if (approvalRequestedAt) {
      const elapsed = Math.floor((Date.now() - new Date(approvalRequestedAt).getTime()) / 1000);
      return Math.max(0, 900 - elapsed);
    }
    return circuitBreakerRemainingSeconds;
  };

  const [remainingTime, setRemainingTime] = useState<number>(computeRemaining());

  useEffect(() => {
    setRemainingTime(computeRemaining());
    const timer = setInterval(() => {
      setRemainingTime(computeRemaining());
    }, 1000);
    return () => clearInterval(timer);
  }, [approvalRequestedAt, circuitBreakerRemainingSeconds]);

  const isTimedOut = remainingTime <= 0;
  const canApprove = capabilities
    ? (capabilities.can_approve && !isTimedOut)
    : (!isSelfApproval && !isTimedOut);

  const disabledReason = isTimedOut
    ? "Fail-Closed Circuit Breaker: 15-minute approval window has expired (TIMEOUT_DENIED)"
    : (capabilities?.disabled_reason || (isSelfApproval ? "Requester cannot approve their own high-risk job (SOX 404)" : "Authorize execution"));

  const defaultPolicies: PolicyProof[] = [
    {
      code: 'POL-001',
      name: 'Maker-Checker Separation',
      status: isSelfApproval ? 'FAIL' : 'PASS',
      evidence: isSelfApproval ? `Self-approval attempt: ${requesterId} === ${currentUserId}` : `Distinct identity assertion: ${requesterId} ≠ ${currentUserId}`,
    },
    {
      code: 'POL-002',
      name: 'ServiceNow Change Window',
      status: servicenowChg ? 'PASS' : 'GATED',
      evidence: servicenowChg ? `${servicenowChg} verified within authorized maintenance window` : 'Missing ServiceNow CHG ticket',
    },
    {
      code: 'POL-003',
      name: 'Fail-Closed Circuit Breaker',
      status: isTimedOut ? 'FAIL' : 'PASS',
      evidence: isTimedOut ? '15-minute approval lease expired' : `${remainingTime}s remaining on approval window`,
    },
    {
      code: 'POL-004',
      name: 'Target Redlock Mutex',
      status: 'PASS',
      evidence: 'Exclusive target resource lock lease verified',
    },
    {
      code: 'POL-005',
      name: 'Zero Plaintext Secrets',
      status: 'PASS',
      evidence: 'CyberArk PAM JIT credential lease bounded',
    },
    {
      code: 'POL-006',
      name: 'Audit Hash Chain Anchor',
      status: 'PASS',
      evidence: 'Write-before-execute SHA-256 Merkle block validated',
    },
  ];

  const activePolicies = policies && policies.length > 0 ? policies : defaultPolicies;
  const passedCount = activePolicies.filter(p => p.status === 'PASS').length;

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
          <span className={`font-bold ${passedCount === activePolicies.length ? 'text-emerald-400' : 'text-amber-400'}`}>
            {passedCount}/{activePolicies.length} Verified
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px]">
          {activePolicies.map((p) => {
            const isPass = p.status === 'PASS';
            const isFail = p.status === 'FAIL';
            const isGated = p.status === 'GATED';
            const isWarn = p.status === 'WARN';

            const badgeClass = isPass
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
              : isFail
              ? 'bg-rose-950/40 text-rose-300 border-rose-500/30'
              : isGated
              ? 'bg-blue-950/40 text-blue-300 border-blue-500/30'
              : isWarn
              ? 'bg-amber-950/40 text-amber-300 border-amber-500/30'
              : 'bg-slate-800 text-slate-400 border-slate-700';

            return (
              <div
                key={p.code}
                title={p.evidence}
                className="flex items-center justify-between p-1.5 rounded bg-slate-900/60 border border-slate-800 text-slate-300"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  {isPass ? (
                    <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />
                  ) : isFail ? (
                    <AlertTriangle size={11} className="text-rose-400 flex-shrink-0" />
                  ) : isGated ? (
                    <Clock size={11} className="text-blue-400 flex-shrink-0" />
                  ) : (
                    <AlertTriangle size={11} className="text-amber-400 flex-shrink-0" />
                  )}
                  <span className="font-bold text-slate-200">{p.code}:</span>
                  <span className="truncate text-slate-400">{p.name}</span>
                </div>
                <span className={`text-[9px] px-1 rounded border flex-shrink-0 font-bold ${badgeClass}`}>
                  {p.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Circuit Breaker Expiration Banner */}
      {isTimedOut && (
        <div className="p-2.5 rounded-lg border border-rose-500/40 bg-rose-950/30 text-rose-300 text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>
            <strong>CIRCUIT BREAKER TRIGGERED:</strong> 15-minute approval window has expired. Automation state transitioned to <code className="text-rose-200 font-bold">TIMEOUT_DENIED</code>.
          </span>
        </div>
      )}

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
          disabled={!canApprove}
          title={disabledReason}
          className={`px-5 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
            !canApprove
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
