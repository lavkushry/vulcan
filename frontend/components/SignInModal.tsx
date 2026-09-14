'use client';

import React, { useState, useEffect } from 'react';
import { Lock, Shield, KeyRound, Check, AlertCircle, RefreshCw, X, User } from 'lucide-react';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';

interface Persona {
  id: string;
  name: string;
  role: string;
  role_badge: string;
  token: string;
  description: string;
}

export function SignInModal() {
  const { isSignInModalOpen, closeSignInModal, loginWithToken, authStatus } = useVulcan();
  const [tokenInput, setTokenInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);

  useEffect(() => {
    if (isSignInModalOpen) {
      api.auth.listTestPersonas()
        .then(data => setPersonas(Array.isArray(data) ? data : []))
        .catch(() => {
          setPersonas([
            { id: 'admin.dave', name: 'Dave Admin', role: 'PLATFORM_ADMIN', role_badge: 'PLATFORM ADMIN', token: 'vlc_test_dave_ci_token', description: 'Full administrative control and resource mutation' },
            { id: 'lead.bob', name: 'Bob Lead', role: 'APPROVING_LEAD', role_badge: 'APPROVING LEAD', token: 'vlc_test_bob_ci_token', description: 'Dual-control approval authority for high-risk jobs' },
            { id: 'sec.carol', name: 'Carol Security', role: 'SECURITY_ADMIN', role_badge: 'SECURITY ADMIN', token: 'vlc_test_carol_ci_token', description: 'Security review and policy enforcement' },
            { id: 'eng.alice', name: 'Alice Engineer', role: 'OPERATOR', role_badge: 'OPERATOR', token: 'vlc_test_alice_ci_token', description: 'Standard operator for routine automation' },
          ]);
        });
    }
  }, [isSignInModalOpen]);

  if (!isSignInModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    const res = await loginWithToken(tokenInput.trim());
    setIsSubmitting(false);

    if (!res.success) {
      setErrorMessage(res.error || 'Authentication failed. Please check your token.');
    }
  };

  const handleSelectPersona = async (p: Persona) => {
    setTokenInput(p.token);
    setIsSubmitting(true);
    setErrorMessage(null);

    const res = await loginWithToken(p.token);
    setIsSubmitting(false);

    if (!res.success) {
      setErrorMessage(res.error || 'Failed to authenticate with persona token.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-lg bg-slate-900 border border-glass-border rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-glass-border flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Lock size={16} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide">Sign in to Vulcan Control Plane</h2>
              <p className="text-[11px] text-slate-400 font-mono">Authenticate to enable live mutations & execution</p>
            </div>
          </div>
          <button
            onClick={closeSignInModal}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 flex-1 overflow-y-auto max-h-[75vh]">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-start gap-2">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5 text-rose-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Token Input Form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <label className="block text-xs font-mono font-semibold text-slate-300">
              Enterprise API Token / Bearer Key
            </label>
            <div className="relative">
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="vlc_... or Bearer token"
                className="w-full bg-slate-950 border border-glass-border rounded-lg px-3.5 py-2.5 text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400 pr-10"
              />
              <KeyRound size={14} className="absolute right-3 top-3 text-slate-500 pointer-events-none" />
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed font-sans">
              Identity, role permissions, and authorization tokens derive strictly from the server-side token map. Client-supplied headers are never trusted.
            </p>
            <button
              type="submit"
              disabled={isSubmitting || !tokenInput.trim()}
              className="w-full py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono text-xs font-bold transition-all disabled:opacity-40 flex items-center justify-center gap-2 cursor-pointer shadow-glow-cyan"
            >
              {isSubmitting ? <RefreshCw size={14} className="animate-spin" /> : <Lock size={14} />}
              <span>Authenticate Session</span>
            </button>
          </form>

          {/* Quick Test Accounts */}
          {personas.length > 0 && (
            <div className="pt-3 border-t border-glass-border">
              <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block mb-2 font-semibold">
                Or Select a Valid Test Identity
              </span>
              <div className="grid grid-cols-1 gap-2">
                {personas.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPersona(p)}
                    disabled={isSubmitting}
                    className="p-3 rounded-lg bg-slate-950/60 hover:bg-slate-800/80 border border-glass-border hover:border-cyan-500/40 text-left transition-all flex items-center justify-between group cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 font-bold text-xs font-mono">
                        {p.name.charAt(0)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-slate-200 group-hover:text-cyan-300 transition-colors">
                            {p.name}
                          </span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400">
                            {p.role_badge}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500">{p.description}</p>
                      </div>
                    </div>
                    <span className="text-[11px] font-mono text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                      <span>Sign in</span>
                      <span>→</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
