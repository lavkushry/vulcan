'use client';

import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Filter, 
  Terminal as TerminalIcon, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ShieldAlert, 
  Layers, 
  RotateCw, 
  Server, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown, 
  Check, 
  X,
  ExternalLink,
  ChevronRight,
  Database,
  Cloud,
  Network,
  Cpu,
  Shield,
  Container,
  Download,
  FileSpreadsheet,
  RefreshCw
} from 'lucide-react';
import { STATUS_STYLE, FILTER_LABELS } from '@/lib/types';
import { timeAgo } from '@/lib/util';

export interface TaskRecord {
  id: string;
  correlation_id: string;
  identifier: string;
  name: string;
  engine: 'ansible' | 'terraform' | string;
  category: string;
  target_resource: string;
  environment: string;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PENDING_APPROVAL' | 'QUEUED' | 'VERIFYING' | 'REJECTED' | 'TIMEOUT_DENIED' | string;
  risk_tier: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  requester_id: string;
  approver_id?: string | null;
  duration_sec?: number;
  created_at: string;
  parameters: Record<string, any>;
  servicenow_chg?: string | null;
  error_message?: string | null;
  diagnostic?: string | null;
  capabilities?: {
    can_approve: boolean;
    can_reject: boolean;
    disabled_reason?: string | null;
  };
}

interface TaskMatrixTableProps {
  tasks: TaskRecord[];
  currentUser: string;
  onOpenTerminal: (task: TaskRecord) => void;
  onApproveTask?: (task: TaskRecord) => void;
  onRejectTask?: (task: TaskRecord) => void;
  onRerunTask?: (task: TaskRecord) => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

const CATEGORIES = [
  { id: 'all', label: 'All Categories', icon: Layers },
  { id: 'cloud', label: 'Cloud / AWS', icon: Cloud },
  { id: 'network', label: 'Network & F5', icon: Network },
  { id: 'database', label: 'Database', icon: Database },
  { id: 'os_patching', label: 'OS Patching', icon: Cpu },
  { id: 'security', label: 'Security & IAM', icon: Shield },
  { id: 'kubernetes', label: 'Kubernetes', icon: Container },
];

const STATUS_FILTERS = [
  { id: 'all', label: 'All Statuses' },
  { id: 'PENDING_APPROVAL', label: 'Pending Approval' },
  { id: 'QUEUED', label: 'Queued' },
  { id: 'RUNNING', label: 'Running' },
  { id: 'VERIFYING', label: 'Verifying' },
  { id: 'SUCCESS', label: 'Success' },
  { id: 'FAILED', label: 'Failed' },
  { id: 'REJECTED', label: 'Rejected' },
  { id: 'TIMEOUT_DENIED', label: 'Timed Out' },
];

export default function TaskMatrixTable({
  tasks,
  currentUser,
  onOpenTerminal,
  onApproveTask,
  onRejectTask,
  onRerunTask,
  onRefresh,
  isLoading = false
}: TaskMatrixTableProps) {
  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEngine, setSelectedEngine] = useState<'all' | 'ansible' | 'terraform'>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedEnv, setSelectedEnv] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  
  // Sort States
  const [sortColumn, setSortColumn] = useState<keyof TaskRecord>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Pagination
  const [pageSize, setPageSize] = useState<number>(25);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Multi-dimensional filtering
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      // Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const haystack = `${task.correlation_id} ${task.identifier} ${task.name} ${task.target_resource} ${task.requester_id} ${task.approver_id || ''} ${task.servicenow_chg || ''} ${task.error_message || ''}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      // Engine
      if (selectedEngine !== 'all' && task.engine !== selectedEngine) return false;

      // Status
      if (selectedStatus !== 'all' && task.status !== selectedStatus) return false;

      // Environment
      if (selectedEnv !== 'all' && task.environment !== selectedEnv) return false;

      // Category
      if (selectedCategory !== 'all') {
        const cat = (task.category || '').toLowerCase();
        if (!cat.includes(selectedCategory.toLowerCase())) return false;
      }

      return true;
    });
  }, [tasks, searchQuery, selectedEngine, selectedStatus, selectedEnv, selectedCategory]);

  // Sorting
  const sortedTasks = useMemo(() => {
    const list = [...filteredTasks];
    list.sort((a, b) => {
      const aVal = a[sortColumn];
      const bVal = b[sortColumn];

      if (aVal === bVal) return 0;
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      let comparison = 0;
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        comparison = aVal.localeCompare(bVal);
      } else if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
    return list;
  }, [filteredTasks, sortColumn, sortDirection]);

  // Paginated slice
  const paginatedTasks = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedTasks.slice(start, start + pageSize);
  }, [sortedTasks, currentPage, pageSize]);

  const totalPages = Math.ceil(sortedTasks.length / pageSize) || 1;

  const handleSort = (col: keyof TaskRecord) => {
    if (sortColumn === col) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(col);
      setSortDirection('desc');
    }
    setCurrentPage(1);
  };

  // CSV Export functionality
  const handleExportCSV = () => {
    const headers = [
      'Correlation ID',
      'Task Name',
      'Identifier',
      'Engine',
      'Category',
      'Target Resource',
      'Environment',
      'Status',
      'Risk Tier',
      'Requester ID',
      'Approver ID',
      'ServiceNow CHG',
      'Duration (sec)',
      'Created At',
      'Error Message'
    ];

    const escapeCsv = (val: any) => {
      if (val === null || val === undefined) return '""';
      const str = String(val).replace(/"/g, '""');
      return `"${str}"`;
    };

    const rows = sortedTasks.map(t => [
      escapeCsv(t.correlation_id),
      escapeCsv(t.name),
      escapeCsv(t.identifier),
      escapeCsv(t.engine),
      escapeCsv(t.category),
      escapeCsv(t.target_resource),
      escapeCsv(t.environment),
      escapeCsv(t.status),
      escapeCsv(t.risk_tier),
      escapeCsv(t.requester_id),
      escapeCsv(t.approver_id || ''),
      escapeCsv(t.servicenow_chg || ''),
      escapeCsv(t.duration_sec || 0),
      escapeCsv(t.created_at),
      escapeCsv(t.error_message || '')
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(r => r.join(','))
    ].join('\r\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `vulcan_tasks_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Status breakdown count badges
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of tasks) {
      counts[t.status] = (counts[t.status] || 0) + 1;
    }
    return counts;
  }, [tasks]);

  return (
    <div className="flex flex-col h-full bg-[#07090E] text-slate-200 overflow-hidden">
      {/* ===================================================================== */}
      {/* FILTER CONTROLS TOOLBAR                                               */}
      {/* ===================================================================== */}
      <div className="p-4 border-b border-slate-800 bg-[#0A0E16] space-y-3">
        {/* Top search & quick action bar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[280px] max-w-xl">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
              placeholder="Search by ID, playbook, target node, ticket (e.g. EXEC-9821, f5-edge, CHG)..."
              className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-[#07090E] border border-slate-700 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Action buttons (Refresh & CSV Export) */}
          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={isLoading}
                title="Refresh task inventory"
                className="px-3 py-2 text-xs font-medium rounded-xl border border-slate-700 bg-slate-800/60 hover:bg-slate-700/80 text-slate-300 flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
                <span>Refresh</span>
              </button>
            )}

            <button
              onClick={handleExportCSV}
              disabled={sortedTasks.length === 0}
              className="px-3.5 py-2 text-xs font-semibold rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-500/40 text-cyan-300 flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV ({sortedTasks.length})</span>
            </button>
          </div>
        </div>

        {/* Secondary Filter Chips */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-xs">
          {/* Engine & Environment dropdowns */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-500 text-[11px] font-mono uppercase tracking-wider">Filters:</span>

            {/* Engine Selector */}
            <div className="flex items-center rounded-lg border border-slate-700 bg-[#07090E] p-0.5">
              {(['all', 'ansible', 'terraform'] as const).map(eng => (
                <button
                  key={eng}
                  onClick={() => { setSelectedEngine(eng); setCurrentPage(1); }}
                  className={`px-2.5 py-1 rounded text-[11px] font-medium capitalize transition-colors ${
                    selectedEngine === eng
                      ? eng === 'ansible' ? 'bg-cyan-500/20 text-cyan-300 font-semibold'
                        : eng === 'terraform' ? 'bg-purple-500/20 text-purple-300 font-semibold'
                        : 'bg-slate-700 text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {eng}
                </button>
              ))}
            </div>

            {/* Environment Selector */}
            <div className="flex items-center rounded-lg border border-slate-700 bg-[#07090E] p-0.5">
              {(['all', 'PROD', 'UAT', 'DEV'] as const).map(env => (
                <button
                  key={env}
                  onClick={() => { setSelectedEnv(env); setCurrentPage(1); }}
                  className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                    selectedEnv === env
                      ? env === 'PROD' ? 'bg-rose-500/20 text-rose-300 font-semibold'
                        : env === 'UAT' ? 'bg-amber-500/20 text-amber-300 font-semibold'
                        : env === 'DEV' ? 'bg-emerald-500/20 text-emerald-300 font-semibold'
                        : 'bg-slate-700 text-white font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {env}
                </button>
              ))}
            </div>

            {/* Category Dropdown */}
            <select
              value={selectedCategory}
              onChange={(e) => { setSelectedCategory(e.target.value); setCurrentPage(1); }}
              className="rounded-lg border border-slate-700 bg-[#07090E] px-2.5 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              {CATEGORIES.map(c => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* Result Counter & Active Filters Clear */}
          <div className="flex items-center gap-3 text-slate-400">
            <span>
              Showing <strong className="text-white">{sortedTasks.length}</strong> of <strong className="text-slate-300">{tasks.length}</strong> tasks
            </span>
            {(searchQuery || selectedEngine !== 'all' || selectedStatus !== 'all' || selectedEnv !== 'all' || selectedCategory !== 'all') && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedEngine('all');
                  setSelectedStatus('all');
                  setSelectedEnv('all');
                  setSelectedCategory('all');
                  setCurrentPage(1);
                }}
                className="text-[11px] text-cyan-400 hover:underline"
              >
                Clear all filters
              </button>
            )}
          </div>
        </div>

        {/* Status Filter Tabs Row */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-1 scrollbar-none border-t border-slate-800/80">
          {STATUS_FILTERS.map(sf => {
            const count = sf.id === 'all' ? tasks.length : (statusCounts[sf.id] || 0);
            const isSelected = selectedStatus === sf.id;
            return (
              <button
                key={sf.id}
                onClick={() => { setSelectedStatus(sf.id); setCurrentPage(1); }}
                className={`px-3 py-1 rounded-lg text-xs font-medium whitespace-nowrap flex items-center gap-1.5 border transition-all ${
                  isSelected
                    ? 'border-cyan-500/60 bg-cyan-500/15 text-cyan-300 shadow-sm'
                    : 'border-slate-800 bg-[#07090E] text-slate-400 hover:border-slate-700 hover:text-slate-300'
                }`}
              >
                <span>{sf.label}</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                  isSelected ? 'bg-cyan-400/20 text-cyan-200' : 'bg-slate-800 text-slate-400'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ===================================================================== */}
      {/* FULL SORTABLE DATA TABLE                                              */}
      {/* ===================================================================== */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse font-sans text-xs">
          <thead className="sticky top-0 z-10 bg-[#0C101A] border-b border-slate-800 text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            <tr>
              <th 
                onClick={() => handleSort('correlation_id')}
                className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Job / Correlation ID</span>
                  {sortColumn === 'correlation_id' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th 
                onClick={() => handleSort('name')}
                className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Automation Task</span>
                  {sortColumn === 'name' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th 
                onClick={() => handleSort('engine')}
                className="py-3 px-3 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Engine</span>
                  {sortColumn === 'engine' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th className="py-3 px-3">Target Node</th>

              <th 
                onClick={() => handleSort('environment')}
                className="py-3 px-3 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Env</span>
                  {sortColumn === 'environment' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th 
                onClick={() => handleSort('status')}
                className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Status</span>
                  {sortColumn === 'status' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th className="py-3 px-4">Requester / Approver</th>

              <th 
                onClick={() => handleSort('created_at')}
                className="py-3 px-4 cursor-pointer hover:text-white transition-colors"
              >
                <div className="flex items-center gap-1.5">
                  <span>Created</span>
                  {sortColumn === 'created_at' ? (
                    sortDirection === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-cyan-400" /> : <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                  ) : <ArrowUpDown className="w-3 h-3 opacity-40" />}
                </div>
              </th>

              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-800/60">
            {paginatedTasks.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-16 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <Filter className="w-8 h-8 text-slate-600 mb-1" />
                    <p className="text-sm font-medium text-slate-400">No automation tasks match your filters</p>
                    <p className="text-xs text-slate-600">Try adjusting your search terms or clearing active filters</p>
                  </div>
                </td>
              </tr>
            ) : (
              paginatedTasks.map(task => {
                const isPending = task.status === 'PENDING_APPROVAL';
                const isRunning = task.status === 'RUNNING' || task.status === 'VERIFYING';
                const isFailed = task.status === 'FAILED';
                const canApprove = task.capabilities ? task.capabilities.can_approve : (currentUser !== task.requester_id);
                const canReject = task.capabilities ? task.capabilities.can_reject : (currentUser !== task.requester_id);
                const disabledReason = task.capabilities?.disabled_reason || (currentUser === task.requester_id ? "Maker-Checker violation: Requester cannot approve own job (SOX 404)" : "Action not permitted");

                return (
                  <tr 
                    key={task.id || task.correlation_id}
                    className="hover:bg-slate-800/40 transition-colors group cursor-pointer"
                    onClick={() => onOpenTerminal(task)}
                  >
                    {/* Correlation ID */}
                    <td className="py-3 px-4 font-mono font-bold text-cyan-400 whitespace-nowrap">
                      {task.correlation_id}
                      {task.servicenow_chg && (
                        <span className="block text-[10px] font-mono text-slate-500 font-normal">
                          {task.servicenow_chg}
                        </span>
                      )}
                    </td>

                    {/* Task Name */}
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-100 group-hover:text-cyan-300 transition-colors">
                        {task.name}
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 truncate max-w-xs">
                        {task.identifier}
                      </div>
                    </td>

                    {/* Engine */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold border ${
                        task.engine === 'ansible'
                          ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400'
                          : 'border-purple-500/30 bg-purple-500/10 text-purple-400'
                      }`}>
                        {task.engine}
                      </span>
                    </td>

                    {/* Target Node */}
                    <td className="py-3 px-3 font-mono text-xs text-slate-300 whitespace-nowrap">
                      {task.target_resource}
                    </td>

                    {/* Environment */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                        task.environment === 'PROD' ? 'bg-rose-950/60 text-rose-400 border border-rose-800/40' :
                        task.environment === 'UAT' ? 'bg-amber-950/60 text-amber-400 border border-amber-800/40' :
                        'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40'
                      }`}>
                        {task.environment}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
                        STATUS_STYLE[task.status] || 'border-slate-700 bg-slate-800 text-slate-300'
                      }`}>
                        {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />}
                        {task.status === 'SUCCESS' && <Check className="w-3 h-3 text-emerald-400" />}
                        {task.status === 'FAILED' && <AlertTriangle className="w-3 h-3 text-rose-400" />}
                        {FILTER_LABELS[task.status] || task.status}
                      </span>
                    </td>

                    {/* Requester & Approver */}
                    <td className="py-3 px-4 text-xs whitespace-nowrap">
                      <div className="text-slate-300 font-mono text-[11px]">
                        req: <span className="text-white">{task.requester_id}</span>
                      </div>
                      {task.approver_id && (
                        <div className="text-slate-500 font-mono text-[10px]">
                          appr: <span className="text-slate-400">{task.approver_id}</span>
                        </div>
                      )}
                    </td>

                    {/* Created At */}
                    <td className="py-3 px-4 text-xs text-slate-400 whitespace-nowrap font-mono">
                      {timeAgo(task.created_at)}
                    </td>

                    {/* Row Action Buttons */}
                    <td 
                      className="py-3 px-4 text-right whitespace-nowrap"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-end gap-1.5">
                        {isPending ? (
                          <>
                            {canApprove ? (
                              onApproveTask && (
                                <button
                                  onClick={() => onApproveTask(task)}
                                  className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm transition-colors"
                                >
                                  Approve
                                </button>
                              )
                            ) : (
                              <span 
                                title={disabledReason}
                                className="px-2 py-1 text-[10px] font-mono rounded bg-amber-500/10 text-amber-400 border border-amber-500/30"
                              >
                                🔒 {disabledReason.includes("Maker-Checker") ? "Requester Locked" : "Gated"}
                              </span>
                            )}

                            {canReject && onRejectTask && (
                              <button
                                onClick={() => onRejectTask(task)}
                                className="px-2.5 py-1 text-xs font-semibold rounded bg-rose-600/80 hover:bg-rose-600 text-white shadow-sm transition-colors"
                              >
                                Reject
                              </button>
                            )}
                          </>
                        ) : null}

                        {/* Terminal Button */}
                        <button
                          onClick={() => onOpenTerminal(task)}
                          title="Open live execution terminal"
                          className="p-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 transition-colors"
                        >
                          <TerminalIcon className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* ===================================================================== */}
      {/* PAGINATION FOOTER                                                     */}
      {/* ===================================================================== */}
      <div className="p-3 px-4 border-t border-slate-800 bg-[#0A0E16] flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span>Rows per page:</span>
          <select
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
            className="rounded border border-slate-700 bg-[#07090E] px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
          >
            {[10, 25, 50, 100].map(size => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
          <span className="ml-2 font-mono">
            {sortedTasks.length > 0 ? (
              `${(currentPage - 1) * pageSize + 1} - ${Math.min(currentPage * pageSize, sortedTasks.length)} of ${sortedTasks.length}`
            ) : '0 of 0'}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
            disabled={currentPage === 1}
            className="px-3 py-1 rounded border border-slate-700 bg-[#07090E] hover:bg-slate-800 text-slate-300 disabled:opacity-40 transition-colors"
          >
            Previous
          </button>
          <span className="px-2 font-mono text-slate-300">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
            disabled={currentPage === totalPages}
            className="px-3 py-1 rounded border border-slate-700 bg-[#07090E] hover:bg-slate-800 text-slate-300 disabled:opacity-40 transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
