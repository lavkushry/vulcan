'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Boxes, Search, RefreshCw, ShieldCheck, AlertTriangle, CheckCircle2,
  ExternalLink, GitPullRequest, GitCommit, Check, X, ShieldAlert,
  Download, ArrowRight, Layers, FileCode, Lock, Filter, Eye, ChevronDown, ChevronUp
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';
import type { CandidateItem, DraftPRResult, ApproveCandidateResult } from '@/lib/types';
import { useRouter } from 'next/navigation';

export default function CurationPage() {
  const { currentUser } = useVulcan();
  const router = useRouter();

  // State
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'terraform_registry' | 'ansible_galaxy'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'CANDIDATE' | 'DRAFTED_PR' | 'CURATED' | 'REJECTED'>('all');
  const [compliantOnly, setCompliantOnly] = useState(false);
  const [expandedDefaults, setExpandedDefaults] = useState<Set<string>>(new Set());

  // Modals state
  const [crawlModalOpen, setCrawlModalOpen] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [crawlTfCount, setCrawlTfCount] = useState(10);
  const [crawlGalaxyCount, setCrawlGalaxyCount] = useState(10);

  const [prModalCandidate, setPrModalCandidate] = useState<CandidateItem | null>(null);
  const [draftingPR, setDraftingPR] = useState(false);
  const [draftResult, setDraftResult] = useState<DraftPRResult | null>(null);
  const [targetRepo, setTargetRepo] = useState('git@github.internal.bank.com:automation/catalog-modules.git');

  const [approveModalCandidate, setApproveModalCandidate] = useState<CandidateItem | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveRepo, setApproveRepo] = useState('git@github.internal.bank.com:automation/catalog-modules.git');
  const [approveSha, setApproveSha] = useState('');
  const [approveError, setApproveError] = useState<string | null>(null);
  const [approveSuccess, setApproveSuccess] = useState<ApproveCandidateResult | null>(null);

  const [rejectModalCandidate, setRejectModalCandidate] = useState<CandidateItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejecting, setRejecting] = useState(false);

  // Load candidates
  const loadCandidates = useCallback(async () => {
    try {
      setLoading(true);
      const items = await api.listCandidates();
      setCandidates(items || []);
    } catch (err) {
      console.error('Failed to load candidates:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  // Telemetry Metrics
  const metrics = useMemo(() => {
    const total = candidates.length;
    const compliant = candidates.filter((c) => c.provenance?.license_compliant).length;
    const drafted = candidates.filter((c) => c.curation_status === 'DRAFTED_PR').length;
    const curated = candidates.filter((c) => c.curation_status === 'CURATED').length;
    const rate = total > 0 ? Math.round((compliant / total) * 100) : 100;
    return { total, compliant, drafted, curated, rate };
  }, [candidates]);

  // Filtered list
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      // Source filter
      if (sourceFilter !== 'all' && c.provenance?.source_registry !== sourceFilter) return false;
      // Status filter
      if (statusFilter !== 'all' && c.curation_status !== statusFilter) return false;
      // Compliance filter
      if (compliantOnly && !c.provenance?.license_compliant) return false;
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = c.name?.toLowerCase().includes(q);
        const matchId = c.identifier?.toLowerCase().includes(q);
        const matchDesc = c.description?.toLowerCase().includes(q);
        const matchUpstream = c.provenance?.upstream_repo?.toLowerCase().includes(q);
        if (!matchName && !matchId && !matchDesc && !matchUpstream) return false;
      }
      return true;
    });
  }, [candidates, sourceFilter, statusFilter, compliantOnly, searchQuery]);

  // Handlers
  const handleCrawl = async () => {
    try {
      setCrawling(true);
      await api.crawlCandidates(crawlTfCount, crawlGalaxyCount);
      setCrawlModalOpen(false);
      await loadCandidates();
    } catch (err: any) {
      alert(`Crawl failed: ${err.message}`);
    } finally {
      setCrawling(false);
    }
  };

  const handleDraftPR = async () => {
    if (!prModalCandidate) return;
    try {
      setDraftingPR(true);
      const res = await api.draftCandidatePR(prModalCandidate.identifier, targetRepo);
      setDraftResult(res);
      await loadCandidates();
    } catch (err: any) {
      alert(`PR drafting failed: ${err.message}`);
    } finally {
      setDraftingPR(false);
    }
  };

  const handleApprove = async () => {
    if (!approveModalCandidate) return;
    setApproveError(null);
    if (!approveSha || !/^[0-9a-f]{40}$/.test(approveSha.trim())) {
      setApproveError('Internal commit SHA must be a valid 40-character hex string (INV-1 invariant).');
      return;
    }
    try {
      setApproving(true);
      const res = await api.approveCandidate(
        approveModalCandidate.identifier,
        currentUser || 'lead.bob',
        approveRepo.trim(),
        approveSha.trim()
      );
      setApproveSuccess(res);
      await loadCandidates();
    } catch (err: any) {
      setApproveError(err.message || 'Approval failed');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectModalCandidate) return;
    if (!rejectReason.trim()) {
      alert('Please provide a rejection reason');
      return;
    }
    try {
      setRejecting(true);
      await api.rejectCandidate(
        rejectModalCandidate.identifier,
        currentUser || 'lead.bob',
        rejectReason.trim()
      );
      setRejectModalCandidate(null);
      setRejectReason('');
      await loadCandidates();
    } catch (err: any) {
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setRejecting(false);
    }
  };

  const toggleDefaults = (id: string) => {
    setExpandedDefaults((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-canvas-void text-slate-100 p-6 space-y-6">
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-glass-border pb-5">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 shadow-glow-amber">
                <Boxes size={24} />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
                  Registry Curation Gate & Candidate Store
                  <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    INV-1 Steel Cage
                  </span>
                </h1>
                <p className="text-sm text-slate-400 mt-0.5">
                  Discovery across public Terraform Registry & Ansible Galaxy. Execution is blocked until human review, license gate, and immutable Git SHA binding.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setRefreshing(true);
                loadCandidates();
              }}
              disabled={loading || refreshing}
              className="px-3.5 py-2 rounded-lg text-xs font-mono font-medium border border-glass-border bg-glass-surface hover:bg-white/[0.04] text-slate-300 flex items-center gap-2 transition"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button
              onClick={() => setCrawlModalOpen(true)}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center gap-2 transition shadow-lg shadow-cyan-500/20"
            >
              <RefreshCw size={14} />
              Crawl Registries
            </button>
          </div>
        </div>

        {/* Telemetry Metrics HUD */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-glass-border bg-glass-surface relative overflow-hidden">
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">Candidate Store</div>
            <div className="text-2xl font-bold text-white mt-1 font-mono">{metrics.total}</div>
            <div className="text-[11px] text-slate-500 mt-1">Modules quarantined from execution</div>
          </div>
          <div className="p-4 rounded-xl border border-glass-border bg-glass-surface relative overflow-hidden">
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">License Policy Gate</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">{metrics.rate}%</div>
            <div className="text-[11px] text-slate-500 mt-1">{metrics.compliant} permissive licenses</div>
          </div>
          <div className="p-4 rounded-xl border border-glass-border bg-glass-surface relative overflow-hidden">
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">Drafted PRs</div>
            <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">{metrics.drafted}</div>
            <div className="text-[11px] text-slate-500 mt-1">Vendoring PRs with SHA-256</div>
          </div>
          <div className="p-4 rounded-xl border border-glass-border bg-glass-surface relative overflow-hidden">
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">Promoted to Curated</div>
            <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">{metrics.curated}</div>
            <div className="text-[11px] text-slate-500 mt-1">Bound to Git 40-char SHA</div>
          </div>
        </div>

        {/* Filters & Search Controls */}
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between p-3.5 rounded-xl border border-glass-border bg-glass-surface">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              placeholder="Search candidate name, namespace, author, or upstream repo..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-lg bg-black/40 border border-glass-border text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Source filter */}
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as any)}
              className="px-3 py-2 rounded-lg bg-black/40 border border-glass-border text-xs font-mono text-slate-300 focus:outline-none"
            >
              <option value="all">All Registries</option>
              <option value="terraform_registry">Terraform Registry</option>
              <option value="ansible_galaxy">Ansible Galaxy</option>
            </select>

            {/* Status filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-3 py-2 rounded-lg bg-black/40 border border-glass-border text-xs font-mono text-slate-300 focus:outline-none"
            >
              <option value="all">All Curation States</option>
              <option value="CANDIDATE">CANDIDATE (Unreviewed)</option>
              <option value="DRAFTED_PR">DRAFTED_PR</option>
              <option value="CURATED">CURATED (Active)</option>
              <option value="REJECTED">REJECTED</option>
            </select>

            {/* Compliance switch */}
            <button
              onClick={() => setCompliantOnly(!compliantOnly)}
              className={`px-3 py-2 rounded-lg text-xs font-mono border transition flex items-center gap-1.5 ${
                compliantOnly
                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                  : 'bg-black/40 border-glass-border text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck size={14} />
              Permissive Licenses Only
            </button>
          </div>
        </div>

        {/* Candidate Cards Grid */}
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-500">
            <RefreshCw size={24} className="animate-spin text-cyan-400" />
            <span className="font-mono text-xs">Accessing candidate isolation store...</span>
          </div>
        ) : filteredCandidates.length === 0 ? (
          <div className="py-16 text-center rounded-xl border border-glass-border bg-glass-surface/50 p-8 space-y-3">
            <Boxes size={40} className="mx-auto text-slate-600" />
            <div className="text-base font-semibold text-slate-300">No candidates match active filters</div>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Run the crawler to pull fresh modules from Ansible Galaxy and the Terraform Registry into the candidate store.
            </p>
            <button
              onClick={() => setCrawlModalOpen(true)}
              className="mt-2 px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 inline-flex items-center gap-2"
            >
              <RefreshCw size={14} />
              Crawl Registries Now
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredCandidates.map((candidate) => {
              const prov = candidate.provenance || ({} as any);
              const isTf = prov.source_registry === 'terraform_registry' || candidate.engine === 'terraform';
              const isCompliant = prov.license_compliant;
              const hasDefaults = prov.suggested_defaults && Object.keys(prov.suggested_defaults).length > 0;
              const isExpanded = expandedDefaults.has(candidate.id);

              return (
                <div
                  key={candidate.id}
                  className="rounded-xl border border-glass-border bg-glass-surface hover:border-slate-700 transition flex flex-col justify-between overflow-hidden group shadow-sm"
                >
                  {/* Card Header */}
                  <div className="p-4 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {/* Registry Badge */}
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                            isTf
                              ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30'
                              : 'bg-red-500/15 text-red-300 border border-red-500/30'
                          }`}
                        >
                          {isTf ? 'Terraform' : 'Galaxy'}
                        </span>

                        {/* Status Badge */}
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                            candidate.curation_status === 'CURATED'
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                              : candidate.curation_status === 'DRAFTED_PR'
                              ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                              : candidate.curation_status === 'REJECTED'
                              ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                              : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {candidate.curation_status === 'CANDIDATE' ? 'QUARANTINED CANDIDATE' : candidate.curation_status}
                        </span>
                      </div>

                      {/* License Badge */}
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-medium flex items-center gap-1 ${
                          isCompliant
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                        }`}
                        title={isCompliant ? 'Permissive license approved' : 'Non-permissive or proprietary license flagged'}
                      >
                        {isCompliant ? <Check size={11} /> : <AlertTriangle size={11} />}
                        {prov.license || 'UNKNOWN'}
                      </span>
                    </div>

                    {/* Title & Identifier */}
                    <div>
                      <h3 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition line-clamp-1">
                        {candidate.name}
                      </h3>
                      <div className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                        {candidate.identifier}
                      </div>
                    </div>

                    {/* Description */}
                    <p className="text-xs text-slate-400 line-clamp-2 min-h-[32px]">
                      {candidate.description || 'No description provided by upstream registry.'}
                    </p>

                    {/* Provenance Metadata */}
                    <div className="pt-2 border-t border-glass-border/60 grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-400">
                      <div>
                        <span className="text-slate-500">Version: </span>
                        <span className="text-slate-300">{prov.version || 'latest'}</span>
                      </div>
                      <div className="flex items-center gap-1 justify-end">
                        <Download size={11} className="text-slate-500" />
                        <span className="text-slate-300">
                          {prov.downloads ? Number(prov.downloads).toLocaleString() : 'N/A'}
                        </span>
                      </div>
                    </div>

                    {/* Suggested Defaults disclosure (Rule 2 / Non-guessing) */}
                    {hasDefaults && (
                      <div className="pt-1">
                        <button
                          onClick={() => toggleDefaults(candidate.id)}
                          className="w-full flex items-center justify-between text-[11px] font-mono text-cyan-400/90 hover:text-cyan-300 bg-cyan-950/20 border border-cyan-900/40 rounded px-2 py-1"
                        >
                          <span className="flex items-center gap-1">
                            <Lock size={10} />
                            Advisory Defaults ({Object.keys(prov.suggested_defaults || {}).length})
                          </span>
                          {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                        {isExpanded && (
                          <div className="mt-1.5 p-2 rounded bg-black/50 border border-glass-border text-[10px] font-mono text-slate-300 space-y-1">
                            <div className="text-slate-500 italic">
                              * Advisory UI hints only. The runtime IntentResolver will strictly fail-closed unless explicitly provided by operator.
                            </div>
                            <div className="max-h-24 overflow-y-auto space-y-0.5">
                              {Object.entries(prov.suggested_defaults || {}).map(([k, v]) => (
                                <div key={k} className="flex justify-between gap-2">
                                  <span className="text-slate-400">{k}:</span>
                                  <span className="text-cyan-300 truncate max-w-[140px]">{JSON.stringify(v)}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Card Footer Actions */}
                  <div className="p-3 bg-black/25 border-t border-glass-border flex items-center justify-between gap-2">
                    {/* External upstream link */}
                    {prov.upstream_repo ? (
                      <a
                        href={prov.upstream_repo}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-slate-400 hover:text-cyan-300 inline-flex items-center gap-1 font-mono"
                      >
                        <ExternalLink size={12} />
                        Upstream
                      </a>
                    ) : (
                      <span />
                    )}

                    {/* Action buttons based on status */}
                    <div className="flex items-center gap-1.5">
                      {candidate.curation_status === 'CURATED' ? (
                        <button
                          onClick={() => router.push(`/actions?selected=${encodeURIComponent(candidate.identifier)}`)}
                          className="px-2.5 py-1 rounded text-xs font-mono font-medium bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30 transition flex items-center gap-1"
                        >
                          <CheckCircle2 size={12} />
                          Active in Catalog
                        </button>
                      ) : candidate.curation_status === 'REJECTED' ? (
                        <span className="text-xs font-mono text-rose-400 flex items-center gap-1">
                          <X size={12} />
                          Rejected
                        </span>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              setRejectModalCandidate(candidate);
                              setRejectReason('');
                            }}
                            className="px-2 py-1 rounded text-xs font-mono text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 transition"
                            title="Reject candidate"
                          >
                            Reject
                          </button>

                          <button
                            onClick={() => {
                              setPrModalCandidate(candidate);
                              setDraftResult(null);
                            }}
                            className="px-2.5 py-1 rounded text-xs font-mono font-medium bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/20 transition flex items-center gap-1"
                            title="Draft internal Git vendoring PR"
                          >
                            <GitPullRequest size={12} />
                            Draft PR
                          </button>

                          <button
                            onClick={() => {
                              setApproveModalCandidate(candidate);
                              setApproveSha('');
                              setApproveError(null);
                              setApproveSuccess(null);
                            }}
                            className="px-2.5 py-1 rounded text-xs font-mono font-semibold bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 transition flex items-center gap-1"
                            title="Promote to CURATED with Git SHA binding"
                          >
                            <GitCommit size={12} />
                            Approve
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* CRAWL MODAL */}
        {crawlModalOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-canvas-void border border-glass-border rounded-xl w-full max-w-md p-5 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-glass-border pb-3">
                <div className="flex items-center gap-2">
                  <RefreshCw size={18} className="text-cyan-400" />
                  <h3 className="text-base font-semibold text-white">Crawl Public Registries</h3>
                </div>
                <button onClick={() => setCrawlModalOpen(false)} className="text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              <p className="text-xs text-slate-400 leading-relaxed">
                Pulls public modules from Ansible Galaxy and the Terraform Registry. Candidates enter the candidate store under <strong className="text-amber-300">CANDIDATE</strong> quarantine, isolated from execution until reviewed.
              </p>

              <div className="space-y-3 font-mono text-xs">
                <div>
                  <label className="text-slate-300 block mb-1">Terraform Registry Modules Count:</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={crawlTfCount}
                    onChange={(e) => setCrawlTfCount(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1">Ansible Galaxy Roles Count:</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={crawlGalaxyCount}
                    onChange={(e) => setCrawlGalaxyCount(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                <button
                  onClick={() => setCrawlModalOpen(false)}
                  disabled={crawling}
                  className="px-3 py-1.5 rounded text-xs font-mono text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCrawl}
                  disabled={crawling}
                  className="px-4 py-2 rounded text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center gap-2"
                >
                  {crawling ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
                  {crawling ? 'Crawling APIs...' : 'Start Registry Crawl'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* DRAFT PR MODAL */}
        {prModalCandidate && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-canvas-void border border-glass-border rounded-xl w-full max-w-lg p-5 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-glass-border pb-3">
                <div className="flex items-center gap-2">
                  <GitPullRequest size={18} className="text-cyan-400" />
                  <h3 className="text-base font-semibold text-white">Draft Internal Git Vendoring PR</h3>
                </div>
                <button onClick={() => setPrModalCandidate(null)} className="text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              <div className="text-xs text-slate-400 space-y-1">
                <div>Candidate: <strong className="text-white">{prModalCandidate.name}</strong></div>
                <div className="font-mono text-[11px] text-slate-500">{prModalCandidate.identifier}</div>
              </div>

              {!draftResult ? (
                <div className="space-y-3 font-mono text-xs">
                  <div>
                    <label className="text-slate-300 block mb-1">Target Corporate Git Repository:</label>
                    <input
                      type="text"
                      value={targetRepo}
                      onChange={(e) => setTargetRepo(e.target.value)}
                      className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200 text-xs"
                    />
                  </div>

                  <div className="p-3 rounded bg-cyan-950/20 border border-cyan-900/40 text-[11px] text-cyan-300 space-y-1">
                    <div>✓ Calculates SHA-256 tarball digest of upstream source</div>
                    <div>✓ Generates isolated PR branch & onboarding README</div>
                    <div>✓ Stubs tfsec / Checkov / ansible-lint compliance checks</div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                    <button
                      onClick={() => setPrModalCandidate(null)}
                      disabled={draftingPR}
                      className="px-3 py-1.5 rounded text-xs font-mono text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDraftPR}
                      disabled={draftingPR}
                      className="px-4 py-2 rounded text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center gap-2"
                    >
                      {draftingPR ? <RefreshCw size={14} className="animate-spin" /> : <GitPullRequest size={14} />}
                      {draftingPR ? 'Generating Draft PR...' : 'Generate PR Artifact'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 font-mono text-xs">
                  <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-1.5">
                    <div className="font-bold flex items-center gap-1.5">
                      <CheckCircle2 size={14} />
                      Vendoring PR Draft Created!
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Branch: <span className="text-cyan-300">{draftResult.branch}</span>
                    </div>
                    <div className="text-[11px] text-slate-300 break-all">
                      Tarball SHA-256: <span className="text-amber-300">{draftResult.tarball_sha256}</span>
                    </div>
                  </div>

                  <div className="p-3 rounded bg-black/40 border border-glass-border space-y-1">
                    <div className="text-[11px] font-semibold text-slate-300 uppercase">Security Scan Checklist</div>
                    {Object.entries(draftResult.security_checklist || {}).map(([k, v]) => (
                      <div key={k} className="flex justify-between text-[11px] text-slate-400">
                        <span>{k}:</span>
                        <span className="text-cyan-400">{v}</span>
                      </div>
                    ))}
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                    <button
                      onClick={() => {
                        setPrModalCandidate(null);
                        setDraftResult(null);
                      }}
                      className="px-4 py-2 rounded text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* APPROVE & COMMIT BINDING MODAL */}
        {approveModalCandidate && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-canvas-void border border-glass-border rounded-xl w-full max-w-lg p-5 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-glass-border pb-3">
                <div className="flex items-center gap-2">
                  <GitCommit size={18} className="text-amber-400" />
                  <h3 className="text-base font-semibold text-white">Approve & Bind Immutable Git SHA</h3>
                </div>
                <button onClick={() => setApproveModalCandidate(null)} className="text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              <div className="text-xs text-slate-400 space-y-1">
                <div>Candidate: <strong className="text-white">{approveModalCandidate.name}</strong></div>
                <div className="font-mono text-[11px] text-slate-500">{approveModalCandidate.identifier}</div>
              </div>

              {!approveSuccess ? (
                <div className="space-y-3 font-mono text-xs">
                  <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] space-y-1">
                    <div className="font-bold flex items-center gap-1">
                      <AlertTriangle size={13} />
                      Steel-Cage Invariant INV-1 Enforcement
                    </div>
                    <div>
                      Approval promotes this module into the active execution catalog. You must provide the verified 40-character commit SHA from your reviewed corporate Git repository.
                    </div>
                  </div>

                  <div>
                    <label className="text-slate-300 block mb-1">Internal Corporate Git Repo:</label>
                    <input
                      type="text"
                      value={approveRepo}
                      onChange={(e) => setApproveRepo(e.target.value)}
                      className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200 text-xs"
                    />
                  </div>

                  <div>
                    <label className="text-slate-300 block mb-1">
                      Reviewed 40-Character Commit SHA <span className="text-rose-400">*</span>:
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. 4fd71b6a1234567890abcdef1234567890abcdef"
                      value={approveSha}
                      onChange={(e) => setApproveSha(e.target.value)}
                      className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200 text-xs font-mono"
                    />
                  </div>

                  {approveError && (
                    <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex items-center gap-1.5">
                      <ShieldAlert size={14} />
                      {approveError}
                    </div>
                  )}

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                    <button
                      onClick={() => setApproveModalCandidate(null)}
                      disabled={approving}
                      className="px-3 py-1.5 rounded text-xs font-mono text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleApprove}
                      disabled={approving}
                      className="px-4 py-2 rounded text-xs font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center gap-2"
                    >
                      {approving ? <RefreshCw size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                      {approving ? 'Promoting...' : 'Confirm Approval & Promote'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 font-mono text-xs">
                  <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-1.5">
                    <div className="font-bold flex items-center gap-1.5">
                      <CheckCircle2 size={14} />
                      Candidate Promoted to CURATED!
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Promoted Identifier: <span className="text-cyan-300">{approveSuccess.promoted_catalog_item?.identifier}</span>
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Locked Commit SHA: <span className="text-amber-300">{approveSuccess.internal_commit_sha}</span>
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Approver: {approveSuccess.approver_id}
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                    <button
                      onClick={() => {
                        setApproveModalCandidate(null);
                        setApproveSuccess(null);
                      }}
                      className="px-4 py-2 rounded text-xs font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950"
                    >
                      Done
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* REJECT MODAL */}
        {rejectModalCandidate && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-canvas-void border border-glass-border rounded-xl w-full max-w-md p-5 space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-glass-border pb-3">
                <div className="flex items-center gap-2">
                  <X size={18} className="text-rose-400" />
                  <h3 className="text-base font-semibold text-white">Reject Candidate Admission</h3>
                </div>
                <button onClick={() => setRejectModalCandidate(null)} className="text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              <div className="text-xs text-slate-400">
                Candidate: <strong className="text-white">{rejectModalCandidate.name}</strong>
              </div>

              <div className="space-y-2 font-mono text-xs">
                <label className="text-slate-300 block">Rejection Reason:</label>
                <textarea
                  rows={3}
                  placeholder="e.g. Non-permissive license, deprecated dependencies, or failed security audit..."
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="w-full px-3 py-2 rounded bg-black/50 border border-glass-border text-slate-200 text-xs focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-glass-border">
                <button
                  onClick={() => setRejectModalCandidate(null)}
                  disabled={rejecting}
                  className="px-3 py-1.5 rounded text-xs font-mono text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReject}
                  disabled={rejecting}
                  className="px-4 py-2 rounded text-xs font-semibold bg-rose-500 hover:bg-rose-400 text-white flex items-center gap-1.5"
                >
                  {rejecting ? <RefreshCw size={14} className="animate-spin" /> : <X size={14} />}
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
