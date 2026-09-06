'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Zap, History, ArrowRight, Sparkles, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { IntentResult, Job } from '@/lib/types';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/lib/env';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  currentUser: string;
}

interface CatalogAction {
  identifier: string;
  name: string;
  engine: string;
  risk_tier: string;
  category: string;
  description: string;
}

export function CommandPalette({ open, onClose, currentUser }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [intentResult, setIntentResult] = useState<IntentResult | null>(null);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [catalogResults, setCatalogResults] = useState<CatalogAction[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery('');
      setIntentResult(null);
      setCatalogResults([]);
      setTimeout(() => inputRef.current?.focus(), 100);
      // Fetch recent jobs
      api.listJobs().then((jobs) => setRecentJobs(jobs.slice(0, 5))).catch(() => {});
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Search catalog + resolve intent on Enter
  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      // Fetch matching catalog items
      const BASE = getApiBaseUrl();
      const res = await fetch(`${BASE}/api/v1/catalog?search=${encodeURIComponent(query.trim())}`);
      if (res.ok) {
        const items = await res.json();
        setCatalogResults(items.slice(0, 6));
      }
      // Also resolve intent via NLP
      const intent = await api.resolveIntent(query.trim());
      setIntentResult(intent);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSearch();
      }
    },
    [handleSearch]
  );

  const navigateToAction = useCallback(
    (identifier: string) => {
      onClose();
      router.push(`/actions?selected=${encodeURIComponent(identifier)}`);
    },
    [onClose, router]
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Palette */}
      <div className="relative w-full max-w-[640px] bg-glass-surface border border-glass-border rounded-xl shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-glass-border">
          <Search size={18} className="text-slate-500 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search actions, run a playbook, or type a command…"
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-600 outline-none"
          />
          {loading && (
            <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          )}
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X size={16} />
          </button>
        </div>

        {/* Intent Match */}
        {intentResult?.match && (
          <div className="px-4 py-3 border-b border-glass-border bg-cyan-500/[0.03]">
            <div className="flex items-center gap-2 text-[10px] font-mono text-cyan-400/70 mb-1.5">
              <Sparkles size={12} />
              <span>BEST MATCH · {Math.round((intentResult.confidence ?? 0) * 100)}% confidence</span>
            </div>
            <button
              onClick={() => navigateToAction(intentResult.match!.identifier)}
              className="w-full flex items-center justify-between group"
            >
              <div>
                <div className="text-sm font-medium text-slate-200 group-hover:text-cyan-300 transition-colors">
                  {intentResult.match.identifier}
                </div>
                <div className="text-xs text-slate-500">{intentResult.match.name}</div>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/50 font-mono text-slate-400">
                  {intentResult.match.engine}
                </span>
                <ArrowRight size={14} className="text-slate-600 group-hover:text-cyan-400 transition-colors" />
              </div>
            </button>
          </div>
        )}

        {/* Catalog Results */}
        {catalogResults.length > 0 && (
          <div className="border-b border-glass-border">
            <div className="px-4 py-1.5 text-[10px] font-mono text-slate-600 uppercase tracking-wider">
              Actions
            </div>
            {catalogResults.map((item) => (
              <button
                key={item.identifier}
                onClick={() => navigateToAction(item.identifier)}
                className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/[0.03] transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <Zap size={14} className="text-slate-600" />
                  <div className="text-left">
                    <div className="text-sm text-slate-300 group-hover:text-cyan-300 transition-colors font-mono">
                      {item.identifier}
                    </div>
                    <div className="text-xs text-slate-600">{item.name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    item.risk_tier === 'HIGH' ? 'bg-rose-400' :
                    item.risk_tier === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400'
                  }`} />
                  <span className="text-[10px] font-mono text-slate-600">{item.engine}</span>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Recent Executions */}
        {!query && recentJobs.length > 0 && (
          <div>
            <div className="px-4 py-1.5 text-[10px] font-mono text-slate-600 uppercase tracking-wider">
              Recent Executions
            </div>
            {recentJobs.map((job) => (
              <button
                key={job.correlation_id}
                onClick={() => {
                  onClose();
                  router.push(`/history?selected=${job.correlation_id}`);
                }}
                className="w-full flex items-center justify-between px-4 py-2 hover:bg-white/[0.03] transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <History size={14} className="text-slate-600" />
                  <div className="text-left">
                    <div className="text-sm text-slate-400 font-mono">{job.correlation_id}</div>
                    <div className="text-xs text-slate-600">{job.name}</div>
                  </div>
                </div>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                  job.status === 'SUCCESS' ? 'border-emerald-500/30 text-emerald-400' :
                  job.status === 'FAILED' ? 'border-rose-500/30 text-rose-400' :
                  job.status === 'RUNNING' ? 'border-cyan-500/30 text-cyan-400' :
                  'border-amber-500/30 text-amber-400'
                }`}>
                  {job.status}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!query && recentJobs.length === 0 && !loading && (
          <div className="px-4 py-8 text-center text-sm text-slate-600">
            Type to search actions or describe what you want to run
          </div>
        )}

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-glass-border flex items-center justify-between text-[10px] text-slate-600 font-mono">
          <span>↵ Search · esc Close</span>
          <span>Powered by Vulcan AI</span>
        </div>
      </div>
    </div>
  );
}
