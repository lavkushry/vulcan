'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  Zap,
  History,
  GitBranch,
  GitMerge,
  Package,
  ShieldCheck,
  KeyRound,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Table2,
  Plug,
  Boxes,
} from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  href: string;
  badge?: number;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'AI Chat Assistant', icon: <Sparkles size={20} className="text-cyan-400" />, href: '/chat' },
  { id: 'actions', label: 'Actions Catalog', icon: <Zap size={20} />, href: '/actions' },
  { id: 'curation', label: 'Registry Curation Gate', icon: <Boxes size={20} className="text-amber-400" />, href: '/curation' },
  { id: 'workflows', label: 'Workflows & Cron', icon: <GitMerge size={20} />, href: '/workflows' },
  { id: 'matrix', label: 'High-Filtered Tasks', icon: <Table2 size={20} />, href: '/matrix' },
  { id: 'history', label: 'Execution History', icon: <History size={20} />, href: '/history' },
  { id: 'rules', label: 'Automation Rules', icon: <GitBranch size={20} />, href: '/rules' },
  { id: 'packs', label: 'Content Packs', icon: <Package size={20} />, href: '/packs' },
  { id: 'integrations', label: 'Connectors & Integrations', icon: <Plug size={20} />, href: '/integrations' },
  { id: 'policies', label: 'Roles & Policies', icon: <KeyRound size={20} />, href: '/policies' },
  { id: 'audit', label: 'Audit & Compliance', icon: <ShieldCheck size={20} />, href: '/audit' },
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} />, href: '/dashboard' },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    const fetchPending = async () => {
      try {
        const jobs = await api.listJobs();
        if (Array.isArray(jobs)) {
          const count = jobs.filter((j) => j.status === 'PENDING_APPROVAL').length;
          setPendingCount(count);
        }
      } catch {
        /* ignore */
      }
    };
    fetchPending();
    const t = setInterval(fetchPending, 5000);
    return () => clearInterval(t);
  }, []);

  const isActive = useCallback(
    (href: string) => {
      if (href === '/chat') {
        return pathname === '/' || pathname === '/chat' || pathname.startsWith('/chat/');
      }
      return pathname === href || pathname.startsWith(href + '/');
    },
    [pathname]
  );

  return (
    <aside
      className={`flex flex-col border-r border-glass-border bg-glass-surface transition-all duration-200 ${
        collapsed ? 'w-[56px]' : 'w-[220px]'
      }`}
    >
      {/* Nav Items */}
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          const badge = item.id === 'history' && pendingCount > 0 ? pendingCount : item.badge;
          return (
            <button
              key={item.id}
              onClick={() => router.push(item.href)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group relative ${
                active
                  ? 'bg-cyan-500/10 text-cyan-400 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
              }`}
            >
              {/* Active indicator bar */}
              {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-cyan-400" />
              )}
              <span className={`flex-shrink-0 ${active ? 'text-cyan-400' : 'text-slate-500 group-hover:text-slate-300'}`}>
                {item.icon}
              </span>
              {!collapsed && (
                <span className="truncate">{item.label}</span>
              )}
              {!collapsed && badge !== undefined && badge > 0 && (
                <span className="ml-auto text-[10px] font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full px-1.5 py-0.5 leading-none animate-pulse">
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className="border-t border-glass-border p-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center py-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
