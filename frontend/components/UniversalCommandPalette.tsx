'use client';

import React, { useState, useEffect } from 'react';
import { Search, Terminal, Database, Cloud, HardDrive, ArrowRight, ShieldCheck, X } from 'lucide-react';

interface CatalogItem {
  id: string;
  identifier: string;
  name: string;
  engine: string;
  risk_tier: string;
  git_commit_sha: string;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPlaybook: (item: CatalogItem) => void;
}

export default function UniversalCommandPalette({
  isOpen,
  onClose,
  onSelectPlaybook
}: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<CatalogItem[]>([
    {
      id: 'cat-f5-renew',
      identifier: 'net-f5-cert-renew',
      name: 'F5 BIG-IP SSL Certificate Renewal',
      engine: 'ansible',
      risk_tier: 'HIGH',
      git_commit_sha: 'a1b2c3d4e5f67890123456789abcdef012345678'
    },
    {
      id: 'cat-db-expand',
      identifier: 'db-expand-tablespace',
      name: 'Database Tablespace Disk Expansion',
      engine: 'ansible',
      risk_tier: 'HIGH',
      git_commit_sha: 'b2c3d4e5f67890123456789abcdef01234567890'
    },
    {
      id: 'cat-vpc-peer',
      identifier: 'cloud-vpc-peering',
      name: 'Cross-Account AWS VPC Peering Connection',
      engine: 'terraform',
      risk_tier: 'MEDIUM',
      git_commit_sha: 'c3d4e5f67890123456789abcdef0123456789012'
    },
    {
      id: 'cat-os-patch',
      identifier: 'os-kernel-patch',
      name: 'Enterprise Linux Kernel Patching (10GB ISO)',
      engine: 'ansible',
      risk_tier: 'HIGH',
      git_commit_sha: 'd4e5f67890123456789abcdef012345678901234'
    }
  ]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onClose();
      }
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  const filtered = items.filter(
    (item) =>
      item.name.toLowerCase().includes(query.toLowerCase()) ||
      item.identifier.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center pt-24 p-4">
      <div className="w-full max-w-2xl bg-canvas-subtle border border-cyan-500/40 rounded-xl shadow-glow-cyan overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Search Header */}
        <div className="flex items-center px-4 py-3 border-b border-glass-border">
          <Search className="w-5 h-5 text-cyan-400 mr-3" />
          <input
            type="text"
            placeholder="Type a natural language intent or playbook key (e.g. 'renew cert' or 'f5')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none font-mono"
          />
          <button onClick={onClose} className="text-slate-500 hover:text-white ml-2">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-xs font-mono text-slate-500">
              No matching playbooks found in catalog.
            </div>
          ) : (
            filtered.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  onSelectPlaybook(item);
                  onClose();
                }}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-glass-raised border border-transparent hover:border-cyan-500/30 cursor-pointer transition-all group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded bg-cyan-950/60 border border-cyan-500/30 flex items-center justify-center text-cyan-400 group-hover:shadow-glow-cyan">
                    <Terminal className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white group-hover:text-cyan-300">
                      {item.name}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 flex items-center gap-2 mt-0.5">
                      <span>{item.identifier}</span>
                      <span>•</span>
                      <span className="text-slate-500">SHA: {item.git_commit_sha.substring(0, 8)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 font-mono text-xs">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      item.risk_tier === 'HIGH'
                        ? 'bg-rose-950/50 text-rose-300 border border-rose-500/30'
                        : 'bg-cyan-950/50 text-cyan-300 border border-cyan-500/30'
                    }`}
                  >
                    {item.risk_tier}
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-glass-border px-4 py-2 bg-canvas-void text-[11px] font-mono text-slate-500 flex items-center justify-between">
          <span>HNSW Cosine + BM25 Hybrid Ranker Active</span>
          <span>Press ESC to exit</span>
        </div>
      </div>
    </div>
  );
}
