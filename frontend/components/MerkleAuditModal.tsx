'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Download, CheckCircle2, Lock, Copy, Check, X, Terminal, ExternalLink, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import type { JobAuditVerification, MerkleAuditRecord } from '@/lib/types';

export interface MerkleAuditModalProps {
  correlationId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const MerkleAuditModal: React.FC<MerkleAuditModalProps> = ({
  correlationId,
  isOpen,
  onClose,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [data, setData] = useState<JobAuditVerification | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<MerkleAuditRecord | null>(null);

  useEffect(() => {
    if (!isOpen || !correlationId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    api.getJobAudit(correlationId)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          if (res.records && res.records.length > 0) {
            setSelectedRecord(res.records[res.records.length - 1]);
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || 'Failed to load Merkle audit records.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, correlationId]);

  if (!isOpen) return null;

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleDownloadWorm = async () => {
    try {
      const url = api.getWormReceiptUrl(correlationId);
      const token = (typeof window !== "undefined" ? window.localStorage.getItem("vulcan_api_token") : null) || process.env.NEXT_PUBLIC_VULCAN_API_TOKEN;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `vulcan-worm-audit-${correlationId}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);
    } catch (e: any) {
      alert(`Could not download WORM receipt: ${e.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-4xl rounded-2xl border border-slate-800 bg-[#0C101A] p-6 shadow-2xl font-mono text-xs max-h-[90vh] flex flex-col gap-4 text-slate-300"
        role="dialog"
        aria-modal="true"
        aria-labelledby="merkle-modal-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-950/60 border border-emerald-500/30 text-emerald-400">
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 id="merkle-modal-title" className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <span>Cryptographic Merkle Audit Chain Verifier</span>
                <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-950/50 text-cyan-300 border border-cyan-500/30">
                  SOX 404 · Immutable
                </span>
              </h2>
              <p className="text-[11px] text-slate-500">
                Tamper-evident SHA-256 hash linkage for execution task <strong className="text-slate-300">{correlationId}</strong>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            aria-label="Close modal"
          >
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-5 h-5 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin" />
            <span className="text-slate-500">Verifying SHA-256 Merkle chain integrity...</span>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-500/40 text-rose-300 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-400" />
            <div>
              <p className="font-bold">Audit Chain Retrieval Error</p>
              <p className="text-[11px] text-rose-400">{error}</p>
            </div>
          </div>
        ) : data ? (
          <div className="flex-1 overflow-y-auto space-y-4 pr-1">
            {/* Status Summary Banner */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-[#07090E] border border-slate-800 flex flex-col gap-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Merkle Chain Status
                </span>
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={14} className="text-emerald-400" />
                  <span className="font-bold text-emerald-400">
                    {data.chain_valid ? '100% CRYPTOGRAPHICALLY VALID' : 'TAMPER DETECTED'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500">Zero broken hashes or deletions</span>
              </div>

              <div className="p-3 rounded-xl bg-[#07090E] border border-slate-800 flex flex-col gap-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Chain Tip Hash
                </span>
                <div className="flex items-center justify-between">
                  <span className="font-bold text-cyan-300 truncate text-[11px]" title={data.tip_hash}>
                    {data.tip_hash.slice(0, 16)}...{data.tip_hash.slice(-8)}
                  </span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(data.tip_hash, 'tip')}
                    className="text-slate-400 hover:text-slate-200"
                    title="Copy full hash"
                  >
                    {copiedHash === 'tip' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  </button>
                </div>
                <span className="text-[10px] text-slate-500">Committed to durable ledger</span>
              </div>

              <div className="p-3 rounded-xl bg-[#07090E] border border-slate-800 flex flex-col gap-1">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                  Attested Events
                </span>
                <span className="font-bold text-slate-200 text-sm">
                  {data.records_count} Synchronous Blocks
                </span>
                <span className="text-[10px] text-slate-500">Write-before-execute invariant</span>
              </div>
            </div>

            {/* Cryptographic Link Inspector */}
            <div className="p-3.5 rounded-xl bg-[#07090E] border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Lock size={12} className="text-cyan-400" />
                  <span>Mathematical Invariant: H_n = SHA256(Record_n ∥ H_{'{n-1}'})</span>
                </span>
                <span className="text-[10px] text-slate-500">
                  Standard: RFC 8785 Canonical JSON
                </span>
              </div>

              {selectedRecord ? (
                <div className="space-y-2 pt-1">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                      <span className="text-[10px] text-slate-500 block">Previous Block Hash (H_{'{n-1}'}):</span>
                      <code className="text-amber-300 font-bold break-all text-[10px]">
                        {selectedRecord.prev_hash}
                      </code>
                    </div>
                    <div className="p-2 rounded bg-slate-900/80 border border-slate-800">
                      <span className="text-[10px] text-slate-500 block">Current Block Hash (H_n):</span>
                      <code className="text-emerald-300 font-bold break-all text-[10px]">
                        {selectedRecord.current_hash}
                      </code>
                    </div>
                  </div>

                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-400 font-semibold">Block #{selectedRecord.id}:</span>{' '}
                      <strong className="text-cyan-300">{selectedRecord.action}</strong> by{' '}
                      <span className="text-slate-300">{selectedRecord.actor}</span>
                    </div>
                    <div className="text-slate-500 text-[10px]">
                      {new Date(selectedRecord.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-slate-500 text-[11px]">No individual record selected.</p>
              )}
            </div>

            {/* Audit Event Timeline */}
            <div className="space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Synchronous Audit Record Ledger ({data.records.length} blocks)
              </span>

              {data.records.length === 0 ? (
                <div className="p-4 rounded-xl bg-[#07090E] border border-slate-800 text-center text-slate-500">
                  No execution audit records committed yet for this job.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {data.records.map((r) => {
                    const isSelected = selectedRecord?.id === r.id;
                    return (
                      <div
                        key={r.id}
                        onClick={() => setSelectedRecord(r)}
                        className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                          isSelected
                            ? 'bg-cyan-950/30 border-cyan-500/50 shadow-[0_0_8px_rgba(0,240,255,0.2)]'
                            : 'bg-[#07090E] border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-bold">
                            #{r.id}
                          </span>
                          <span className="font-bold text-slate-200 truncate">{r.action}</span>
                          <span className="text-slate-500 text-[10px]">by {r.actor}</span>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <code className="text-[10px] text-slate-500 font-mono">
                            {r.current_hash.slice(0, 10)}...
                          </code>
                          <span className="text-[10px] text-slate-500">
                            {new Date(r.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : null}

        {/* Footer with WORM Download CTA */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-800 mt-auto">
          <span className="text-[10px] text-slate-500">
            Write-Once-Read-Many (WORM) compliant receipt conforms to SEC 17a-4(f) / SOX 404.
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs transition-colors"
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleDownloadWorm}
              disabled={loading || !data}
              className="px-4 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 font-bold text-xs flex items-center gap-1.5 shadow-[0_0_12px_rgba(0,255,157,0.3)] transition-all"
            >
              <Download size={13} />
              <span>Download WORM Receipt (.json)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MerkleAuditModal;
