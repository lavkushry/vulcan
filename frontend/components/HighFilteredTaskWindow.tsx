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
  Radio
} from 'lucide-react';

export interface TaskRecord {
  id: string;
  correlation_id: string;
  identifier: string;
  name: string;
  engine: 'ansible' | 'terraform' | string;
  category: string;
  target_resource: string;
  environment: string;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PENDING_APPROVAL' | 'QUEUED' | string;
  risk_tier: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  requester_id: string;
  approver_id?: string | null;
  duration_sec: number;
  created_at: string;
  parameters: Record<string, any>;
  error_message?: string | null;
}

interface HighFilteredTaskWindowProps {
  tasks: TaskRecord[];
  onOpenTerminal: (task: TaskRecord) => void;
  onApproveTask?: (correlationId: string) => Promise<void>;
  onRerunTask?: (task: TaskRecord) => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

const CATEGORIES = [
  { id: 'all', label: 'All Categories', icon: Layers },
  { id: 'cloud', label: 'Cloud / AWS / Azure', icon: Cloud },
  { id: 'network', label: 'Network & F5', icon: Network },
  { id: 'database', label: 'Database', icon: Database },
  { id: 'os_patching', label: 'OS Patching', icon: Cpu },
  { id: 'security', label: 'Security & IAM', icon: Shield },
  { id: 'kubernetes', label: 'Kubernetes', icon: Container },
];

export default function HighFilteredTaskWindow({
  tasks,
  onOpenTerminal,
  onApproveTask,
  onRerunTask,
  onRefresh,
  isLoading = false
}: HighFilteredTaskWindowProps) {
  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEngine, setSelectedEngine] = useState<'all' | 'ansible' | 'terraform'>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedEnv, setSelectedEnv] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [sortField, setSortField] = useState<'created_at' | 'name' | 'status'>('created_at');
  const [sortAsc, setSortAsc] = useState(false);

  // Compute live counts
  const counts = useMemo(() => {
    const running = tasks.filter(t => t.status === 'RUNNING').length;
    const success = tasks.filter(t => t.status === 'SUCCESS').length;
    const failed = tasks.filter(t => t.status === 'FAILED').length;
    const pending = tasks.filter(t => t.status === 'PENDING_APPROVAL').length;
    const ansible = tasks.filter(t => t.engine === 'ansible').length;
    const terraform = tasks.filter(t => t.engine === 'terraform').length;
    return { running, success, failed, pending, ansible, terraform, total: tasks.length };
  }, [tasks]);

  // Apply multidimensional filtering
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      // Engine filter
      if (selectedEngine !== 'all' && task.engine !== selectedEngine) return false;
      // Status filter
      if (selectedStatus !== 'all' && task.status !== selectedStatus) return false;
      // Environment filter
      if (selectedEnv !== 'all' && task.environment !== selectedEnv) return false;
      // Category filter
      if (selectedCategory !== 'all' && task.category !== selectedCategory) return false;
      // Text Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const haystack = `${task.correlation_id} ${task.id} ${task.name} ${task.identifier} ${task.target_resource} ${task.requester_id} ${task.category}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    }).sort((a, b) => {
      if (sortField === 'created_at') {
        const dateA = new Date(a.created_at || '').getTime();
        const dateB = new Date(b.created_at || '').getTime();
        return sortAsc ? dateA - dateB : dateB - dateA;
      }
      if (sortField === 'name') {
        return sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
      }
      if (sortField === 'status') {
        return sortAsc ? a.status.localeCompare(b.status) : b.status.localeCompare(a.status);
      }
      return 0;
    });
  }, [tasks, selectedEngine, selectedStatus, selectedEnv, selectedCategory, searchQuery, sortField, sortAsc]);

  const hasActiveFilters = searchQuery !== '' || selectedEngine !== 'all' || selectedStatus !== 'all' || selectedEnv !== 'all' || selectedCategory !== 'all';

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedEngine('all');
    setSelectedStatus('all');
    setSelectedEnv('all');
    setSelectedCategory('all');
  };

  const formatDuration = (sec: number) => {
    if (!sec || sec <= 0) return '-';
    if (sec < 60) return `${sec}s`;
    const mins = Math.floor(sec / 60);
    const remainder = sec % 60;
    return `${mins}m ${remainder}s`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'RUNNING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 shadow-glow-cyan/20 animate-pulse">
            <Radio className="w-3 h-3 text-cyan-400" />
            <span>RUNNING</span>
          </span>
        );
      case 'SUCCESS':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>SUCCESS</span>
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-500/40">
            <AlertTriangle className="w-3 h-3 text-rose-400" />
            <span>FAILED</span>
          </span>
        );
      case 'PENDING_APPROVAL':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-950/80 text-amber-300 border border-amber-500/40">
            <Clock className="w-3 h-3 text-amber-400" />
            <span>PENDING SIGN-OFF</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono text-slate-400 bg-white/5 border border-glass-border">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-glass-surface/90 border border-glass-border rounded-2xl overflow-hidden shadow-glass-panel backdrop-blur-xl">
      {/* Top Telemetry HUD */}
      <div className="p-4 border-b border-glass-border/80 bg-canvas-subtle/50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-500/20 to-blue-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-glow-purple/20">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-white tracking-wide">
                High-Filtered Task Window
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {filteredTasks.length} of {tasks.length}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Multi-dimensional filter across 100–1,000+ automated operations
            </p>
          </div>
        </div>

        {/* Status Count Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <button
            onClick={() => setSelectedStatus(selectedStatus === 'RUNNING' ? 'all' : 'RUNNING')}
            className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 border transition-all ${
              selectedStatus === 'RUNNING'
                ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-glow-cyan/20'
                : 'bg-white/5 border-glass-border text-cyan-400 hover:bg-cyan-500/10'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
            <span>Running ({counts.running})</span>
          </button>

          <button
            onClick={() => setSelectedStatus(selectedStatus === 'SUCCESS' ? 'all' : 'SUCCESS')}
            className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 border transition-all ${
              selectedStatus === 'SUCCESS'
                ? 'bg-emerald-500/20 border-emerald-400 text-emerald-300'
                : 'bg-white/5 border-glass-border text-emerald-400 hover:bg-emerald-500/10'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>Passed ({counts.success})</span>
          </button>

          <button
            onClick={() => setSelectedStatus(selectedStatus === 'FAILED' ? 'all' : 'FAILED')}
            className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 border transition-all ${
              selectedStatus === 'FAILED'
                ? 'bg-rose-500/20 border-rose-400 text-rose-300'
                : 'bg-white/5 border-glass-border text-rose-400 hover:bg-rose-500/10'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-rose-400"></span>
            <span>Failed ({counts.failed})</span>
          </button>

          {counts.pending > 0 && (
            <button
              onClick={() => setSelectedStatus(selectedStatus === 'PENDING_APPROVAL' ? 'all' : 'PENDING_APPROVAL')}
              className={`px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5 border transition-all ${
                selectedStatus === 'PENDING_APPROVAL'
                  ? 'bg-amber-500/20 border-amber-400 text-amber-300'
                  : 'bg-white/5 border-glass-border text-amber-400 hover:bg-amber-500/10'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              <span>Pending ({counts.pending})</span>
            </button>
          )}

          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
              title="Refresh task stream"
            >
              <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Multi-Dimensional Filter Bar */}
      <div className="p-3 bg-canvas-void/50 border-b border-glass-border space-y-2.5">
        {/* Row 1: Search & Engine Tabs */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tasks by ID, playbook name, target host, requester..."
              className="w-full bg-black/60 border border-glass-border focus:border-cyan-400 text-slate-100 text-xs rounded-xl pl-9 pr-8 py-2 placeholder:text-slate-500 focus:outline-none transition-colors font-mono"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Engine Segmented Control */}
          <div className="flex items-center bg-black/40 border border-glass-border rounded-xl p-0.5">
            <button
              onClick={() => setSelectedEngine('all')}
              className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg transition-all ${
                selectedEngine === 'all'
                  ? 'bg-white/15 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All ({counts.total})
            </button>
            <button
              onClick={() => setSelectedEngine('ansible')}
              className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                selectedEngine === 'ansible'
                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60 shadow-glow-crimson/20'
                  : 'text-slate-400 hover:text-rose-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Ansible ({counts.ansible})
            </button>
            <button
              onClick={() => setSelectedEngine('terraform')}
              className={`px-3 py-1.5 text-xs font-mono font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                selectedEngine === 'terraform'
                  ? 'bg-purple-950/80 text-purple-300 border border-purple-800/60 shadow-glow-purple/20'
                  : 'text-slate-400 hover:text-purple-300'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-purple-500"></span>
              Terraform ({counts.terraform})
            </button>
          </div>

          {/* Environment Filter Dropdown */}
          <select
            value={selectedEnv}
            onChange={(e) => setSelectedEnv(e.target.value)}
            className="bg-black/60 border border-glass-border focus:border-cyan-400 text-slate-200 text-xs rounded-xl px-3 py-2 font-mono focus:outline-none transition-colors"
          >
            <option value="all">All Envs</option>
            <option value="PROD">PROD</option>
            <option value="UAT">UAT</option>
            <option value="DEV">DEV</option>
            <option value="STAGING">STAGING</option>
          </select>
        </div>

        {/* Row 2: Category Chips & Reset */}
        <div className="flex items-center justify-between gap-2 overflow-x-auto no-scrollbar pt-0.5">
          <div className="flex items-center gap-1.5">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              const isSelected = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono whitespace-nowrap border transition-all ${
                    isSelected
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-glow-cyan/20'
                      : 'bg-white/5 border-glass-border text-slate-400 hover:text-slate-200 hover:bg-white/10'
                  }`}
                >
                  <Icon className="w-3 h-3" />
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>

          {hasActiveFilters && (
            <button
              onClick={resetFilters}
              className="text-[11px] font-mono text-rose-400 hover:text-rose-300 flex items-center gap-1 px-2 py-0.5 rounded border border-rose-500/30 bg-rose-950/20 whitespace-nowrap"
            >
              <X className="w-3 h-3" />
              <span>Clear Filters</span>
            </button>
          )}
        </div>
      </div>

      {/* High-Density Task List Table */}
      <div className="flex-1 overflow-y-auto">
        {filteredTasks.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-slate-500 space-y-2">
            <Filter className="w-8 h-8 stroke-1 text-slate-600" />
            <p className="text-xs font-mono">No automation tasks match the active filters.</p>
            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="text-xs font-mono text-cyan-400 hover:underline"
              >
                Reset all filters
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-glass-border/40">
            {filteredTasks.map((task) => (
              <div 
                key={task.id || task.correlation_id}
                className="p-3.5 hover:bg-white/[0.03] transition-colors group flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
              >
                {/* Left Side: Engine, Correlation ID, Playbook Info */}
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  {/* Engine Icon Badge */}
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-mono font-bold mt-0.5 ${
                    task.engine === 'ansible'
                      ? 'bg-rose-950/70 text-rose-400 border border-rose-800/60'
                      : 'bg-purple-950/70 text-purple-400 border border-purple-800/60'
                  }`}>
                    {task.engine === 'ansible' ? 'A' : 'TF'}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <span className="text-xs font-mono font-bold text-white tracking-wide">
                        {task.correlation_id}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/5 text-slate-400 border border-glass-border">
                        {task.category}
                      </span>
                      <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-semibold ${
                        task.environment === 'PROD' 
                          ? 'bg-rose-950/60 text-rose-300 border border-rose-800/50' 
                          : 'bg-cyan-950/60 text-cyan-300 border border-cyan-800/50'
                      }`}>
                        {task.environment}
                      </span>
                      {getStatusBadge(task.status)}
                    </div>

                    <h4 className="text-xs font-semibold text-slate-200 truncate group-hover:text-cyan-300 transition-colors">
                      {task.name}
                    </h4>

                    <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400 mt-1 flex-wrap">
                      <span className="flex items-center gap-1 text-slate-300">
                        <Server className="w-3 h-3 text-cyan-400" />
                        {task.target_resource}
                      </span>
                      <span>By: {task.requester_id}</span>
                      <span>Duration: {formatDuration(task.duration_sec)}</span>
                      {task.created_at && (
                        <span>{new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      )}
                    </div>

                    {task.error_message && (
                      <p className="text-[11px] text-rose-400 font-mono mt-1 bg-rose-950/30 px-2 py-0.5 rounded border border-rose-800/40">
                        {task.error_message}
                      </p>
                    )}
                  </div>
                </div>

                {/* Right Side: Operational Action Buttons */}
                <div className="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
                  {/* Maker-Checker Approve Button (if pending) */}
                  {task.status === 'PENDING_APPROVAL' && onApproveTask && (
                    <button
                      onClick={() => onApproveTask(task.correlation_id)}
                      className="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 transition-colors flex items-center gap-1"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Approve</span>
                    </button>
                  )}

                  {/* Re-run Button */}
                  {onRerunTask && task.status !== 'RUNNING' && (
                    <button
                      onClick={() => onRerunTask(task)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 border border-glass-border transition-colors"
                      title="Re-run this automation"
                    >
                      <RotateCw className="w-3.5 h-3.5" />
                    </button>
                  )}

                  {/* Open Terminal / Logs */}
                  <button
                    onClick={() => onOpenTerminal(task)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-semibold bg-glass-raised hover:bg-white/10 text-cyan-300 border border-cyan-500/30 hover:border-cyan-400 transition-all shadow-glow-cyan/10"
                  >
                    <TerminalIcon className="w-3.5 h-3.5" />
                    <span>Live Terminal</span>
                    <ChevronRight className="w-3 h-3 text-cyan-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer Status Summary */}
      <div className="p-3 border-t border-glass-border/80 bg-canvas-subtle/70 flex items-center justify-between text-xs font-mono text-slate-400">
        <div>
          <span>Enterprise Control Plane // </span>
          <span className="text-slate-300">{tasks.length} total automations registered</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-cyan-400">● 60 FPS Telemetry</span>
          <span>Fail-closed Mode: ACTIVE</span>
        </div>
      </div>
    </div>
  );
}
