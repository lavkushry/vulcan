'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
  Zap,
  History,
  GitMerge,
  ShieldCheck,
  KeyRound,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Plug,
  Boxes,
} from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useVulcan } from '@/lib/context';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  href: string;
  badge?: number;
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: 'New Request', icon: <Sparkles size={18} className="text-cyan-400" />, href: '/chat' },
  { id: 'activity', label: 'Activity', icon: <History size={18} />, href: '/history' },
  { id: 'catalog', label: 'Catalog', icon: <Zap size={18} />, href: '/actions' },
  { id: 'connections', label: 'Connections', icon: <Plug size={18} />, href: '/settings/external-resources' },
];

const ADMIN_NAV_ITEMS: NavItem[] = [
  { id: 'policies', label: 'Policies & Roles', icon: <KeyRound size={16} />, href: '/policies' },
  { id: 'audit', label: 'Audit & Compliance', icon: <ShieldCheck size={16} />, href: '/audit' },
  { id: 'curation', label: 'Curation Gate', icon: <Boxes size={16} className="text-amber-400" />, href: '/curation' },
  { id: 'workflows', label: 'Schedules & Cron', icon: <GitMerge size={16} />, href: '/workflows' },
  { id: 'dashboard', label: 'Infrastructure', icon: <LayoutDashboard size={16} />, href: '/dashboard' },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { hasPermission, isDemoMode } = useVulcan();
  const [collapsed, setCollapsed] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const canAccessAdmin = isDemoMode || hasPermission('admin:access') || hasPermission('policy:manage') || hasPermission('audit:view');

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
        return pathname === '/' || pathname === '/chat' || pathname.startsWith('/chat/') || pathname === '/agents' || pathname.startsWith('/agents');
      }
      if (href === '/history') {
        return pathname === '/history' || pathname.startsWith('/history/') || pathname === '/matrix' || pathname.startsWith('/matrix');
      }
      if (href === '/actions') {
        return pathname === '/actions' || pathname.startsWith('/actions/') || pathname === '/packs' || pathname.startsWith('/packs');
      }
      if (href === '/settings/external-resources') {
        return pathname === '/settings/external-resources' || pathname.startsWith('/settings/external-resources') || pathname === '/integrations' || pathname.startsWith('/integrations');
      }
      if (href === '/workflows') {
        return pathname === '/workflows' || pathname.startsWith('/workflows/') || pathname === '/rules' || pathname.startsWith('/rules');
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
      {/* Primary Nav Items */}
      <nav className="flex-1 py-3 space-y-1 px-2 overflow-y-auto">
        <div className="space-y-0.5">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            const badge = item.id === 'activity' && pendingCount > 0 ? pendingCount : item.badge;
            return (
              <button
                key={item.id}
                onClick={() => router.push(item.href)}
                title={collapsed ? item.label : undefined}
                aria-label={item.label}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group relative ${
                  active
                    ? 'bg-cyan-500/10 text-cyan-400 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
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
                  <span className="ml-auto text-[10px] font-mono bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-full px-1.5 py-0.5 leading-none">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Administration Section */}
        {canAccessAdmin && (
          <div className="pt-4 mt-3 border-t border-glass-border/60">
            {!collapsed && (
              <div className="px-3 pb-1.5 text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
                Administration
              </div>
            )}
            <div className="space-y-0.5">
              {ADMIN_NAV_ITEMS.map((item) => {
                const active = isActive(item.href);
                return (
                  <button
                    key={item.id}
                    onClick={() => router.push(item.href)}
                    title={collapsed ? item.label : undefined}
                    aria-label={item.label}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all group relative ${
                      active
                        ? 'bg-cyan-500/10 text-cyan-400'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                    }`}
                  >
                    {active && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 rounded-r-full bg-cyan-400" />
                    )}
                    <span className={`flex-shrink-0 ${active ? 'text-cyan-400' : 'text-slate-500 group-hover:text-slate-300'}`}>
                      {item.icon}
                    </span>
                    {!collapsed && (
                      <span className="truncate">{item.label}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </nav>

      {/* Collapse Toggle */}
      <div className="border-t border-glass-border p-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center py-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/[0.04] transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
