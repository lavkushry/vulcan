'use client';

import React, { useState, useEffect, useMemo, useCallback, Suspense } from 'react';
import {
  Search, FolderTree, Zap, Play, ChevronRight, ChevronDown,
  Network, Cloud, Database, Monitor, Shield, Boxes,
  AlertTriangle
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';
import type { Job } from '@/lib/types';
import { useSearchParams } from 'next/navigation';
import { getApiBaseUrl } from '@/lib/env';

interface CatalogItem {
  id: string;
  identifier: string;
  name: string;
  engine: string;
  risk_tier: string;
  requires_maker_checker: boolean;
  requires_chg: boolean;
  input_schema: Record<string, any>;
  category: string;
  description: string;
  tags: string[];
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  network: <Network size={14} />,
  cloud: <Cloud size={14} />,
  database: <Database size={14} />,
  os_patching: <Monitor size={14} />,
  security: <Shield size={14} />,
  kubernetes: <Boxes size={14} />,
};

function ActionsContent() {
  const { currentUser } = useVulcan();
  const searchParams = useSearchParams();
  const preselected = searchParams.get('selected');

  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(preselected);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionSearch, setActionSearch] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [paramValues, setParamValues] = useState<Record<string, any>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Fetch catalog
  useEffect(() => {
    const BASE = getApiBaseUrl();
    fetch(`${BASE}/api/v1/catalog`)
      .then((r) => r.json())
      .then((items) => {
        setCatalog(items);
        // Auto-expand all categories
        const cats = new Set(items.map((i: CatalogItem) => i.category));
        setExpandedCategories(cats as Set<string>);
      })
      .catch(() => {});
  }, []);

  // Group by category
  const categories = useMemo(() => {
    const map: Record<string, CatalogItem[]> = {};
    catalog.forEach((item) => {
      const cat = item.category || 'general';
      if (!map[cat]) map[cat] = [];
      map[cat].push(item);
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [catalog]);

  // Filtered actions
  const filteredActions = useMemo(() => {
    let items = selectedCategory ? catalog.filter((i) => i.category === selectedCategory) : catalog;
    const q = actionSearch.trim().toLowerCase();
    if (q) {
      items = items.filter((i) =>
        `${i.identifier} ${i.name} ${i.description} ${i.tags.join(' ')}`.toLowerCase().includes(q)
      );
    }
    return items;
  }, [catalog, selectedCategory, actionSearch]);

  // Selected action detail
  const activeAction = useMemo(() => catalog.find((i) => i.identifier === selectedAction) ?? null, [catalog, selectedAction]);

  // Reset params when action changes
  useEffect(() => {
    if (activeAction) {
      const defaults: Record<string, any> = {};
      const schema = activeAction.input_schema;
      if (schema?.properties) {
        Object.entries(schema.properties).forEach(([key, spec]: [string, any]) => {
          if (spec.default !== undefined) defaults[key] = spec.default;
        });
      }
      setParamValues(defaults);
      setSubmitResult(null);
    }
  }, [activeAction]);

  const toggleCategory = useCallback((cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  // Submit
  const handleRun = useCallback(async () => {
    if (!activeAction) return;
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const job = await api.createJob({
        identifier: activeAction.identifier,
        parameters: paramValues,
        requester_id: currentUser,
        servicenow_chg: paramValues.servicenow_chg || null,
      });
      setSubmitResult({
        ok: true,
        message: `Job ${job.correlation_id} created — status: ${job.status}`,
      });
    } catch (e: any) {
      setSubmitResult({ ok: false, message: e?.message || 'Failed to create job' });
    } finally {
      setSubmitting(false);
    }
  }, [activeAction, paramValues, currentUser]);

  // Render param input by schema type
  const renderParamInput = useCallback(
    (key: string, spec: any) => {
      const value = paramValues[key] ?? '';
      const isRequired = activeAction?.input_schema?.required?.includes(key);

      if (spec.enum) {
        return (
          <div key={key} className="space-y-1">
            <label className="text-xs text-slate-500">
              {key}{isRequired && <span className="text-rose-400 ml-0.5">*</span>}
              {spec.description && <span className="ml-2 text-slate-700">— {spec.description}</span>}
            </label>
            <div className="flex flex-wrap gap-1.5">
              {spec.enum.map((opt: string) => (
                <button
                  key={opt}
                  onClick={() => setParamValues((p) => ({ ...p, [key]: opt }))}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono border transition-colors ${
                    value === opt
                      ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
                      : 'border-glass-border bg-glass-surface text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        );
      }

      if (spec.type === 'boolean') {
        return (
          <div key={key} className="flex items-center gap-3">
            <button
              onClick={() => setParamValues((p) => ({ ...p, [key]: !p[key] }))}
              className={`w-9 h-5 rounded-full border transition-colors relative ${
                value ? 'border-cyan-500/40 bg-cyan-500/20' : 'border-glass-border bg-glass-surface'
              }`}
            >
              <div className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
                value ? 'left-4 bg-cyan-400' : 'left-0.5 bg-slate-600'
              }`} />
            </button>
            <label className="text-xs text-slate-400">
              {key}{spec.description && <span className="ml-2 text-slate-600">— {spec.description}</span>}
            </label>
          </div>
        );
      }

      if (spec.type === 'integer' || spec.type === 'number') {
        return (
          <div key={key} className="space-y-1">
            <label className="text-xs text-slate-500">
              {key}{isRequired && <span className="text-rose-400 ml-0.5">*</span>}
              {spec.description && <span className="ml-2 text-slate-700">— {spec.description}</span>}
            </label>
            <input
              type="number"
              value={value}
              min={spec.minimum}
              max={spec.maximum}
              onChange={(e) => setParamValues((p) => ({ ...p, [key]: parseInt(e.target.value) || 0 }))}
              placeholder={spec.default?.toString() ?? ''}
              className="w-full px-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-300 font-mono outline-none focus:border-cyan-500/40 transition-colors"
            />
          </div>
        );
      }

      // Default: string
      return (
        <div key={key} className="space-y-1">
          <label className="text-xs text-slate-500">
            {key}{isRequired && <span className="text-rose-400 ml-0.5">*</span>}
            {spec.description && <span className="ml-2 text-slate-700">— {spec.description}</span>}
          </label>
          <input
            type="text"
            value={value}
            onChange={(e) => setParamValues((p) => ({ ...p, [key]: e.target.value }))}
            placeholder={spec.default ?? ''}
            className="w-full px-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-300 font-mono outline-none focus:border-cyan-500/40 transition-colors"
          />
        </div>
      );
    },
    [paramValues, activeAction]
  );

  return (
    <div className="flex h-full">
      {/* ──── PACK TREE (Left) ──── */}
      <div className="w-[220px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/30">
        <div className="px-3 py-2.5 border-b border-glass-border">
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-glass-surface border border-glass-border">
            <Search size={13} className="text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search packs…"
              className="flex-1 bg-transparent text-xs text-slate-300 placeholder-slate-600 outline-none"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto py-1">
          {/* All Actions */}
          <button
            onClick={() => setSelectedCategory(null)}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
              !selectedCategory ? 'bg-cyan-500/[0.06] text-cyan-400' : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            <FolderTree size={14} />
            <span>All Actions</span>
            <span className="ml-auto text-[10px] text-slate-600">{catalog.length}</span>
          </button>
          {categories
            .filter(([cat]) => !searchQuery || cat.toLowerCase().includes(searchQuery.toLowerCase()))
            .map(([cat, items]) => (
            <div key={cat}>
              <button
                onClick={() => {
                  toggleCategory(cat);
                  setSelectedCategory(cat);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors ${
                  selectedCategory === cat ? 'bg-cyan-500/[0.06] text-cyan-400' : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                {expandedCategories.has(cat) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span className="text-slate-500">{CATEGORY_ICONS[cat] || <FolderTree size={14} />}</span>
                <span className="truncate">{cat}</span>
                <span className="ml-auto text-[10px] text-slate-600">{items.length}</span>
              </button>
              {expandedCategories.has(cat) && selectedCategory === cat && (
                <div className="ml-5 border-l border-glass-border/50">
                  {items.map((item) => (
                    <button
                      key={item.identifier}
                      onClick={() => setSelectedAction(item.identifier)}
                      className={`w-full text-left px-3 py-1.5 text-[11px] font-mono truncate transition-colors ${
                        selectedAction === item.identifier
                          ? 'text-cyan-400 bg-cyan-500/[0.04]'
                          : 'text-slate-600 hover:text-slate-400'
                      }`}
                    >
                      {item.identifier.replace(`${cat}-`, '')}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ──── ACTION LIST (Center) ──── */}
      <div className="w-[300px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/20">
        <div className="px-3 py-2.5 border-b border-glass-border">
          <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-glass-surface border border-glass-border">
            <Search size={13} className="text-slate-500" />
            <input
              type="text"
              value={actionSearch}
              onChange={(e) => setActionSearch(e.target.value)}
              placeholder="Filter actions…"
              className="flex-1 bg-transparent text-xs text-slate-300 placeholder-slate-600 outline-none"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {filteredActions.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-slate-600">No actions found</div>
          )}
          {filteredActions.map((item) => (
            <button
              key={item.identifier}
              onClick={() => setSelectedAction(item.identifier)}
              className={`w-full text-left px-3 py-2.5 border-b border-glass-border/30 transition-colors relative ${
                selectedAction === item.identifier
                  ? 'bg-cyan-500/[0.06]'
                  : 'hover:bg-white/[0.02]'
              }`}
            >
              {selectedAction === item.identifier && (
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
              )}
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-xs font-mono text-slate-300">{item.identifier}</span>
                <span className={`ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  item.risk_tier === 'HIGH' ? 'bg-rose-400' :
                  item.risk_tier === 'MEDIUM' ? 'bg-amber-400' : 'bg-emerald-400'
                }`} />
              </div>
              <div className="text-[11px] text-slate-600 truncate">{item.name}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[10px] font-mono px-1 py-0.5 rounded border border-glass-border text-slate-600">
                  {item.engine}
                </span>
                {item.requires_maker_checker && (
                  <span className="text-[10px] font-mono text-amber-500/60">SoD</span>
                )}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ──── ACTION DETAIL + RUN FORM (Right) ──── */}
      <div className="flex-1 overflow-y-auto p-5">
        {!activeAction ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600">
            <Zap size={40} className="mb-3 opacity-30" />
            <p className="text-sm">Select an action to view details and run</p>
            <p className="text-xs mt-1 text-slate-700">Browse the pack tree or search for an action</p>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto space-y-5">
            {/* Action header */}
            <div>
              <h2 className="text-lg font-mono text-slate-200 mb-1">{activeAction.identifier}</h2>
              <p className="text-sm text-slate-400">{activeAction.name}</p>
              {activeAction.description && (
                <p className="text-xs text-slate-600 mt-2">{activeAction.description}</p>
              )}
            </div>

            {/* Metadata badges */}
            <div className="flex flex-wrap gap-2">
              <span className="px-2 py-1 rounded-md border border-slate-700 bg-slate-800/50 text-xs font-mono text-slate-400">
                Runner: {activeAction.engine}
              </span>
              <span className={`px-2 py-1 rounded-md border text-xs font-mono ${
                activeAction.risk_tier === 'HIGH' ? 'border-rose-500/30 text-rose-400 bg-rose-500/10' :
                activeAction.risk_tier === 'MEDIUM' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
              }`}>
                Risk: {activeAction.risk_tier}
              </span>
              <span className="px-2 py-1 rounded-md border border-slate-700 bg-slate-800/50 text-xs font-mono text-slate-400">
                Pack: {activeAction.category}
              </span>
              {activeAction.requires_maker_checker && (
                <span className="px-2 py-1 rounded-md border border-amber-500/30 bg-amber-500/10 text-xs font-mono text-amber-400">
                  Requires Approval
                </span>
              )}
              {activeAction.requires_chg && (
                <span className="px-2 py-1 rounded-md border border-purple-500/30 bg-purple-500/10 text-xs font-mono text-purple-400">
                  Requires CHG
                </span>
              )}
            </div>

            {/* Parameter form */}
            <div className="bg-glass-surface border border-glass-border rounded-lg p-4 space-y-4">
              <h3 className="text-xs font-mono text-slate-500 uppercase tracking-wider">Parameters</h3>
              {activeAction.input_schema?.properties ? (
                Object.entries(activeAction.input_schema.properties).map(([key, spec]: [string, any]) =>
                  renderParamInput(key, spec)
                )
              ) : (
                <p className="text-xs text-slate-600">No parameters required</p>
              )}

              {/* ServiceNow CHG field — always show if requires_chg */}
              {activeAction.requires_chg && (
                <div className="space-y-1 pt-2 border-t border-glass-border">
                  <label className="text-xs text-purple-400/70">
                    ServiceNow CHG<span className="text-rose-400 ml-0.5">*</span>
                  </label>
                  <input
                    type="text"
                    value={paramValues.servicenow_chg ?? ''}
                    onChange={(e) => setParamValues((p) => ({ ...p, servicenow_chg: e.target.value }))}
                    placeholder="CHG-XXXXX"
                    className="w-full px-3 py-1.5 rounded-lg bg-glass-surface border border-purple-500/20 text-xs text-slate-300 font-mono outline-none focus:border-purple-500/40 transition-colors"
                  />
                </div>
              )}
            </div>

            {/* Run button */}
            <button
              onClick={handleRun}
              disabled={submitting}
              className={`w-full py-3 rounded-lg text-sm font-mono flex items-center justify-center gap-2 transition-all ${
                submitting
                  ? 'bg-slate-800 text-slate-500 cursor-wait'
                  : activeAction.risk_tier === 'HIGH'
                    ? 'bg-amber-500/20 border border-amber-500/30 text-amber-400 hover:bg-amber-500/30'
                    : 'bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/30'
              }`}
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  <Play size={16} />
                  {activeAction.risk_tier === 'HIGH' ? 'Run — Requires Approval' : 'Run Immediately'}
                </>
              )}
            </button>

            {/* Submit result */}
            {submitResult && (
              <div className={`px-4 py-3 rounded-lg text-xs font-mono ${
                submitResult.ok
                  ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                  : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
              }`}>
                {submitResult.message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ActionsPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="flex-1 flex items-center justify-center text-xs text-slate-500 font-mono">Loading Actions Catalog…</div>}>
        <ActionsContent />
      </Suspense>
    </AppShell>
  );
}
