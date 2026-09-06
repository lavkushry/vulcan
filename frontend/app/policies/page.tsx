'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import {
  KeyRound, Shield, Lock, Play, CheckCircle2, XCircle, AlertTriangle,
  RefreshCw, Check, ArrowRight, FileCode, Users, Sliders, ToggleLeft, ToggleRight
} from 'lucide-react';
import { RoleDefinition, PolicyRule, PolicyEvaluationResult } from '@/lib/types';
import { DEMO_USERS } from '@/lib/api';

const PERMISSION_COLUMNS = [
  { key: 'catalog:read', label: 'Discover Catalog' },
  { key: 'job:request', label: 'Request Job' },
  { key: 'dry_run:execute', label: 'Dry Run' },
  { key: 'job:approve', label: 'Maker-Checker Approve' },
  { key: 'job:reject', label: 'Reject Job' },
  { key: 'workflow:dispatch', label: 'DAG Workflows' },
  { key: 'cron:manage', label: 'Cron Scheduler' },
  { key: 'integrations:manage', label: 'Connectors Hub' },
  { key: 'audit:verify', label: 'Merkle Audit' },
  { key: 'policy:manage', label: 'Policy Manage' },
  { key: 'compliance:export', label: 'SOX Export' },
];

function PoliciesContent() {
  const [activeTab, setActiveTab] = useState<'roles' | 'policies' | 'simulator'>('roles');
  const [roles, setRoles] = useState<RoleDefinition[]>([]);
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [expandedRego, setExpandedRego] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  // Simulator State
  const [simUser, setSimUser] = useState<string>('eng.alice');
  const [simAction, setSimAction] = useState<string>('net-f5-cert-renew');
  const [simEnv, setSimEnv] = useState<string>('PROD');
  const [simRisk, setSimRisk] = useState<string>('HIGH');
  const [simChg, setSimChg] = useState<string>('CHG-2026-9901');
  const [simApprover, setSimApprover] = useState<string>('none');
  const [simFreeze, setSimFreeze] = useState<boolean>(false);
  const [simEmergency, setSimEmergency] = useState<boolean>(false);
  const [simSecretLeak, setSimSecretLeak] = useState<boolean>(false);

  const [evalResult, setEvalResult] = useState<PolicyEvaluationResult | null>(null);
  const [evaluating, setEvaluating] = useState<boolean>(false);

  const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [rRes, pRes] = await Promise.all([
        fetch(`${BASE}/api/v1/roles`),
        fetch(`${BASE}/api/v1/policies`),
      ]);
      if (rRes.ok) setRoles(await rRes.json());
      if (pRes.ok) setPolicies(await pRes.json());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [BASE]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTogglePolicy = async (policyId: string) => {
    try {
      const res = await fetch(`${BASE}/api/v1/policies/${policyId}/toggle`, { method: 'POST' });
      if (res.ok) {
        fetchData();
      }
    } catch {
      /* ignore */
    }
  };

  const handleRunSimulation = async () => {
    setEvaluating(true);
    try {
      const params: Record<string, any> = { hostname: 'f5-edge-01.corp.internal' };
      if (simSecretLeak) {
        params.private_key = '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0unauthorized';
      }

      const payload = {
        user_id: simUser,
        action_identifier: simAction,
        environment: simEnv,
        risk_tier: simRisk,
        parameters: params,
        servicenow_chg: simChg.trim() ? simChg.trim() : null,
        is_freeze_active: simFreeze,
        is_emergency: simEmergency,
        approver_id: simApprover !== 'none' ? simApprover : null,
      };

      const res = await fetch(`${BASE}/api/v1/policies/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setEvalResult(await res.json());
      }
    } catch {
      /* ignore */
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#07090E] text-slate-100 font-sans overflow-hidden">
      {/* Top Banner */}
      <div className="border-b border-glass-border bg-[#0C101A]/70 backdrop-blur-xl px-6 py-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-glow-cyan">
              <KeyRound size={18} />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
                Enterprise Roles & Policy-as-Code Governance
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 font-mono">
                  PNC BANK OPA/REGO
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Deterministic RBAC permissions, Four-Eyes separation of duties, and real-time attribute evaluation simulator
              </p>
            </div>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-900/80 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveTab('roles')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'roles'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Users size={14} />
              <span>Roles & Permissions ({roles.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('policies')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'policies'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Lock size={14} />
              <span>Active Guardrails ({policies.length})</span>
            </button>
            <button
              onClick={() => {
                setActiveTab('simulator');
                if (!evalResult) handleRunSimulation();
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === 'simulator'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sliders size={14} />
              <span>Policy Simulator</span>
            </button>
          </div>

          <button
            onClick={fetchData}
            disabled={loading}
            className="p-1.5 rounded-lg border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700 transition-colors"
            title="Refresh policies"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ========================================================================= */}
        {/* TAB 1: ROLES & PERMISSIONS MATRIX */}
        {/* ========================================================================= */}
        {activeTab === 'roles' && (
          <div className="space-y-6">
            {/* Personas Cards */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              {DEMO_USERS.map((user) => (
                <div
                  key={user.id}
                  className="rounded-xl border border-glass-border bg-[#0C101A]/80 p-4 flex flex-col justify-between hover:border-slate-700 transition-all"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs font-bold text-slate-200">{user.label}</span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                          user.role === 'APPROVING_LEAD'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : user.role === 'SECURITY_ADMIN'
                            ? 'border-purple-500/30 bg-purple-500/10 text-purple-300'
                            : user.role === 'PLATFORM_ADMIN'
                            ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                            : user.role === 'AUDITOR'
                            ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
                            : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
                        }`}
                      >
                        {user.roleBadge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">{user.desc}</p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-slate-800 text-[10px] font-mono text-slate-500">
                    ID: {user.id}
                  </div>
                </div>
              ))}
            </div>

            {/* Permissions Matrix Table */}
            <div className="rounded-xl border border-glass-border bg-[#0C101A]/80 overflow-hidden shadow-2xl">
              <div className="px-5 py-3 border-b border-glass-border bg-slate-900/40 flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-cyan-300">
                  ENTERPRISE CAPABILITIES MATRIX (5 ROLES × 11 PERMISSIONS)
                </span>
                <span className="text-[11px] text-slate-500">
                  Strictly enforced across API routes and CLI runners
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400">
                      <th className="py-3 px-4 font-medium">CAPABILITY / PERMISSION</th>
                      {roles.map((r) => (
                        <th key={r.role} className="py-3 px-4 font-medium text-center">
                          {r.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {PERMISSION_COLUMNS.map((col) => (
                      <tr key={col.key} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-200">{col.label}</div>
                          <div className="text-[10px] text-slate-500">{col.key}</div>
                        </td>
                        {roles.map((r) => {
                          const has = r.permissions.includes(col.key) || r.permissions.includes('*');
                          return (
                            <td key={r.role} className="py-3 px-4 text-center">
                              {has ? (
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                                  <Check size={13} />
                                </span>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: ACTIVE GUARDRAIL POLICIES */}
        {/* ========================================================================= */}
        {activeTab === 'policies' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              {policies.map((p) => {
                const isExpanded = expandedRego[p.policy_id] || false;
                return (
                  <div
                    key={p.policy_id}
                    className="rounded-xl border border-glass-border bg-[#0C101A]/80 p-5 hover:border-slate-700 transition-all"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-9 h-9 rounded-lg flex items-center justify-center mt-0.5 ${
                            p.enforcement_level === 'MANDATORY_BLOCK'
                              ? 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
                              : 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
                          }`}
                        >
                          <Lock size={18} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-bold text-slate-200">{p.name}</span>
                            <span className="font-mono text-[10px] px-2 py-0.5 rounded border border-slate-700 bg-slate-800 text-slate-400">
                              {p.policy_id}
                            </span>
                            <span
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                                p.enforcement_level === 'MANDATORY_BLOCK'
                                  ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                                  : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                              }`}
                            >
                              {p.enforcement_level}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{p.description}</p>
                          <div className="flex items-center gap-2 mt-2">
                            {p.tags.map((t) => (
                              <span
                                key={t}
                                className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400"
                              >
                                #{t}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Controls */}
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() =>
                            setExpandedRego((prev) => ({ ...prev, [p.policy_id]: !prev[p.policy_id] }))
                          }
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs font-mono text-slate-400 hover:text-slate-200 hover:border-slate-700 transition-colors"
                        >
                          <FileCode size={13} />
                          <span>{isExpanded ? 'Hide Rego' : 'View Rego'}</span>
                        </button>
                        <button
                          onClick={() => handleTogglePolicy(p.policy_id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
                            p.is_active
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                              : 'border-slate-800 bg-slate-900 text-slate-500 hover:text-slate-300'
                          }`}
                        >
                          {p.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                          <span>{p.is_active ? 'ENFORCED' : 'PAUSED'}</span>
                        </button>
                      </div>
                    </div>

                    {/* Expandable Rego Code Viewer */}
                    {isExpanded && (
                      <div className="mt-4 pt-4 border-t border-slate-800">
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 mb-1.5">
                          <span>OPA Rego Definition:</span>
                          <span className="text-cyan-400">policy_id: {p.policy_id}</span>
                        </div>
                        <pre className="p-3 rounded-lg bg-[#05070B] border border-slate-800/80 font-mono text-[11px] text-cyan-300 overflow-x-auto">
                          {p.rego_definition}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: LIVE POLICY EVALUATION SIMULATOR */}
        {/* ========================================================================= */}
        {activeTab === 'simulator' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Col: Simulation Controls */}
            <div className="lg:col-span-5 space-y-4">
              <div className="rounded-xl border border-glass-border bg-[#0C101A]/80 p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-xs font-mono font-bold text-slate-200 flex items-center gap-2">
                    <Sliders size={14} className="text-cyan-400" />
                    SIMULATION CONTEXT
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    Real-time Deterministic Evaluation
                  </span>
                </div>

                {/* Actor */}
                <div>
                  <label className="text-[11px] font-mono text-slate-400 mb-1 block">
                    Requesting User (Actor):
                  </label>
                  <select
                    value={simUser}
                    onChange={(e) => setSimUser(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/50"
                  >
                    {DEMO_USERS.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.label} ({u.roleBadge})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Action Identifier */}
                <div>
                  <label className="text-[11px] font-mono text-slate-400 mb-1 block">
                    Catalog Action Identifier:
                  </label>
                  <select
                    value={simAction}
                    onChange={(e) => setSimAction(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/50"
                  >
                    <option value="net-f5-cert-renew">net-f5-cert-renew (F5 SSL Cert Renewal)</option>
                    <option value="os-rhel-kernel-patch">os-rhel-kernel-patch (RHEL Kernel Patch)</option>
                    <option value="cloud-aws-vpc-peering">cloud-aws-vpc-peering (Terraform VPC Peering)</option>
                    <option value="db-postgres-vacuum-analyze">db-postgres-vacuum-analyze (PostgreSQL Vacuum)</option>
                    <option value="cloud-s3-golden-upload">cloud-s3-golden-upload (10GB S3 Storage Upload)</option>
                  </select>
                </div>

                {/* Environment & Risk Tier */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-mono text-slate-400 mb-1 block">Environment:</label>
                    <div className="flex gap-1.5">
                      {['DEV', 'UAT', 'PROD'].map((env) => (
                        <button
                          key={env}
                          type="button"
                          onClick={() => setSimEnv(env)}
                          className={`flex-1 py-1.5 rounded text-xs font-mono font-medium transition-all ${
                            simEnv === env
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                              : 'bg-slate-900 text-slate-400 border border-slate-800'
                          }`}
                        >
                          {env}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-[11px] font-mono text-slate-400 mb-1 block">Risk Tier:</label>
                    <div className="flex gap-1.5">
                      {['LOW', 'MEDIUM', 'HIGH'].map((risk) => (
                        <button
                          key={risk}
                          type="button"
                          onClick={() => setSimRisk(risk)}
                          className={`flex-1 py-1.5 rounded text-xs font-mono font-medium transition-all ${
                            simRisk === risk
                              ? risk === 'HIGH'
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : 'bg-slate-900 text-slate-400 border border-slate-800'
                          }`}
                        >
                          {risk}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* ServiceNow CHG */}
                <div>
                  <label className="text-[11px] font-mono text-slate-400 mb-1 block">
                    ServiceNow Change Request (CHG):
                  </label>
                  <input
                    type="text"
                    value={simChg}
                    onChange={(e) => setSimChg(e.target.value)}
                    placeholder="e.g. CHG-2026-9901 (or leave blank to test failure)"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/50"
                  />
                </div>

                {/* Approver Selection */}
                <div>
                  <label className="text-[11px] font-mono text-slate-400 mb-1 block">
                    Sign-off Approver (Maker-Checker Check):
                  </label>
                  <select
                    value={simApprover}
                    onChange={(e) => setSimApprover(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 outline-none focus:border-cyan-500/50"
                  >
                    <option value="none">None (Not Yet Approved)</option>
                    <option value="lead.bob">lead.bob (Approving Lead - Distinct Signer)</option>
                    <option value="eng.alice">eng.alice (Same User - Self Approval Attempt)</option>
                    <option value="sec.carol">sec.carol (Security Officer)</option>
                  </select>
                </div>

                {/* Checkbox Toggles */}
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <label className="flex items-center gap-2 text-xs font-mono text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simFreeze}
                      onChange={(e) => setSimFreeze(e.target.checked)}
                      className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                    />
                    <span>Simulate Active Operational Freeze Window (POL-005)</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs font-mono text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simEmergency}
                      onChange={(e) => setSimEmergency(e.target.checked)}
                      className="rounded bg-slate-900 border-slate-700 text-cyan-500"
                    />
                    <span>Apply Emergency Override Tag (Bypass Freeze)</span>
                  </label>

                  <label className="flex items-center gap-2 text-xs font-mono text-rose-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simSecretLeak}
                      onChange={(e) => setSimSecretLeak(e.target.checked)}
                      className="rounded bg-slate-900 border-slate-700 text-rose-500"
                    />
                    <span>Inject Plaintext RSA Private Key into Payload (POL-003)</span>
                  </label>
                </div>

                {/* Evaluate Action Button */}
                <button
                  onClick={handleRunSimulation}
                  disabled={evaluating}
                  className="w-full py-2.5 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 font-mono text-xs font-bold hover:bg-cyan-500/30 transition-all flex items-center justify-center gap-2 shadow-glow-cyan"
                >
                  <Play size={14} className={evaluating ? 'animate-spin' : ''} />
                  <span>{evaluating ? 'EVALUATING POLICIES…' : 'RUN POLICY EVALUATION'}</span>
                </button>
              </div>
            </div>

            {/* Right Col: Simulation Results */}
            <div className="lg:col-span-7">
              {evalResult ? (
                <div className="rounded-xl border border-glass-border bg-[#0C101A]/90 p-6 space-y-6">
                  {/* Big Verdict Header */}
                  <div
                    className={`rounded-xl border p-5 flex items-center justify-between ${
                      evalResult.decision === 'ALLOW'
                        ? 'border-emerald-500/40 bg-emerald-500/10'
                        : evalResult.decision === 'REQUIRE_APPROVAL'
                        ? 'border-amber-500/40 bg-amber-500/10'
                        : 'border-rose-500/40 bg-rose-500/10'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-10 h-10 rounded-full flex items-center justify-center ${
                          evalResult.decision === 'ALLOW'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : evalResult.decision === 'REQUIRE_APPROVAL'
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-rose-500/20 text-rose-400'
                        }`}
                      >
                        {evalResult.decision === 'ALLOW' && <CheckCircle2 size={24} />}
                        {evalResult.decision === 'REQUIRE_APPROVAL' && <AlertTriangle size={24} />}
                        {evalResult.decision === 'DENY' && <XCircle size={24} />}
                      </div>
                      <div>
                        <div className="text-[11px] font-mono text-slate-400">EVALUATION OUTCOME</div>
                        <div
                          className={`text-lg font-bold font-mono tracking-wider ${
                            evalResult.decision === 'ALLOW'
                              ? 'text-emerald-300'
                              : evalResult.decision === 'REQUIRE_APPROVAL'
                              ? 'text-amber-300'
                              : 'text-rose-300'
                          }`}
                        >
                          {evalResult.decision === 'ALLOW' && 'ALLOW — EXECUTION PERMITTED'}
                          {evalResult.decision === 'REQUIRE_APPROVAL' && 'REQUIRE_APPROVAL — LEAD SIGN-OFF REQUIRED'}
                          {evalResult.decision === 'DENY' && 'DENY — POLICY VIOLATION BLOCKED'}
                        </div>
                      </div>
                    </div>

                    <div className="text-right font-mono text-xs text-slate-400">
                      <div>Role: <span className="text-cyan-400">{evalResult.user_role}</span></div>
                      <div>Actor: <span className="text-slate-200">{evalResult.user_id}</span></div>
                    </div>
                  </div>

                  {/* Reasons & Citations */}
                  {evalResult.reasons.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-xs font-mono text-slate-400 font-semibold block">
                        POLICY DECISION RATIONALE:
                      </span>
                      <div className="space-y-1.5">
                        {evalResult.reasons.map((r, i) => (
                          <div
                            key={i}
                            className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-xs font-mono text-slate-300 flex items-start gap-2"
                          >
                            <ArrowRight size={14} className="text-cyan-400 mt-0.5 shrink-0" />
                            <span>{r}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Policies Breakdown Grid */}
                  <div className="grid grid-cols-3 gap-3 font-mono text-xs">
                    <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                      <div className="text-emerald-400 font-bold mb-1 flex items-center gap-1.5">
                        <CheckCircle2 size={13} />
                        PASSED ({evalResult.passed_policies.length})
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {evalResult.passed_policies.map((p) => (
                          <span key={p} className="px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-300 text-[10px]">
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                      <div className="text-amber-400 font-bold mb-1 flex items-center gap-1.5">
                        <AlertTriangle size={13} />
                        GATED ({evalResult.gated_policies.length})
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {evalResult.gated_policies.length > 0 ? (
                          evalResult.gated_policies.map((p) => (
                            <span key={p} className="px-1.5 py-0.5 rounded bg-amber-950/40 text-amber-300 text-[10px]">
                              {p}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-600 text-[10px]">None</span>
                        )}
                      </div>
                    </div>

                    <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 p-3">
                      <div className="text-rose-400 font-bold mb-1 flex items-center gap-1.5">
                        <XCircle size={13} />
                        DENIED ({evalResult.denied_policies.length})
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {evalResult.denied_policies.length > 0 ? (
                          evalResult.denied_policies.map((p) => (
                            <span key={p} className="px-1.5 py-0.5 rounded bg-rose-950/40 text-rose-300 text-[10px]">
                              {p}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-600 text-[10px]">None</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Telemetry Footer */}
                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-500">
                    <span>Evaluated at: {evalResult.evaluated_at}</span>
                    <span className="text-cyan-400">Target Env: {evalResult.environment}</span>
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-glass-border bg-[#0C101A]/50 p-12 text-center text-slate-500 font-mono text-xs">
                  Adjust simulation parameters on the left and click "RUN POLICY EVALUATION" to inspect the decision tree.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PoliciesPage() {
  return (
    <AppShell>
      <PoliciesContent />
    </AppShell>
  );
}
