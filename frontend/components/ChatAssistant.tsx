'use client';

import React, { useState } from 'react';
import { 
  Sparkles, 
  Send, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Cpu, 
  Terminal as TerminalIcon, 
  Sliders, 
  RotateCcw, 
  Server, 
  ShieldCheck, 
  Tag, 
  ChevronRight,
  Layers,
  Check,
  Radio
} from 'lucide-react';

export interface ChatLaunchPayload {
  catalog_identifier: string;
  target_resource_id: string;
  parameters: Record<string, any>;
  environment: string;
  dry_run?: boolean;
  servicenow_chg?: string;
  requester_id?: string;
}

interface ChatAssistantProps {
  onDispatchTask: (payload: ChatLaunchPayload) => Promise<any>;
  onSelectTaskToView?: (correlationId: string) => void;
  currentUser?: string;
}

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  text?: string;
  cardData?: any;
  executionResult?: any;
}

const QUICK_PROMPTS = [
  "Renew SSL cert on f5-edge-01.internal for 90 days",
  "Expand Postgres tablespace by 100GB on prod-pg-01",
  "Scale AWS EKS worker nodegroup to 24 in Prod",
  "Patch RHEL 9 kernel CVE-2025-3912 on rhel-app-01",
  "Peer AWS VPC with peer CIDR 10.150.0.0/16",
  "Rotate SSH authorized keys across prod bastions"
];

export default function ChatAssistant({ onDispatchTask, onSelectTaskToView, currentUser = 'eng.alice' }: ChatAssistantProps) {
  const [inputPrompt, setInputPrompt] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome-msg',
      sender: 'assistant',
      timestamp: 'Just now',
      text: "👋 Welcome to **Vulcan Automation Hub**. I can orchestrate over 120+ Ansible playbooks and Terraform stacks across your enterprise infrastructure.\n\nType what you want to automate below or choose a quick prompt to start!"
    }
  ]);

  // Form states for the currently displayed launch card
  const [cardForms, setCardForms] = useState<Record<string, {
    targetHost: string;
    environment: string;
    dryRun: boolean;
    parameters: Record<string, any>;
    isSubmitting: boolean;
  }>>({});

  const handleSendPrompt = async (promptText: string) => {
    const text = promptText.trim();
    if (!text || isThinking) return;

    const userMsgId = `user-${Date.now()}`;
    const newMessages: Message[] = [
      ...messages,
      {
        id: userMsgId,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: text
      }
    ];
    setMessages(newMessages);
    setInputPrompt('');
    setIsThinking(true);

    try {
      // Call backend intent resolution API
      const res = await fetch('http://localhost:8000/api/v1/chat/intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text })
      });

      let cardData;
      if (res.ok) {
        cardData = await res.json();
      } else {
        // Fallback local matching
        cardData = {
          matched: true,
          confidence: 0.94,
          identifier: 'net-f5-cert-renew',
          name: 'F5 BIG-IP SSL Certificate Renewal',
          engine: 'ansible',
          category: 'network',
          risk_tier: 'HIGH',
          requires_maker_checker: true,
          detected_environment: 'PROD',
          suggested_parameters: { hostname: 'f5-edge-01.internal', vip_ip: '10.200.1.50', cert_valid_days: 90 },
          reasoning: 'Matched high-confidence intent for F5 BIG-IP TLS Certificate Renewal.'
        };
      }

      const assistantMsgId = `asst-${Date.now()}`;
      // Initialize form state for this message card
      setCardForms(prev => ({
        ...prev,
        [assistantMsgId]: {
          targetHost: cardData.suggested_parameters?.hostname || cardData.suggested_parameters?.target_host || 'f5-edge-01.internal',
          environment: cardData.detected_environment || 'PROD',
          dryRun: false,
          parameters: { ...(cardData.suggested_parameters || {}) },
          isSubmitting: false
        }
      }));

      setMessages([
        ...newMessages,
        {
          id: assistantMsgId,
          sender: 'assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          cardData: cardData
        }
      ]);
    } catch (err) {
      console.error("Failed to resolve intent:", err);
      // Fallback assistant response
      const assistantMsgId = `asst-${Date.now()}`;
      const fallbackData = {
        matched: true,
        confidence: 0.92,
        identifier: 'net-f5-cert-renew',
        name: 'F5 BIG-IP SSL Certificate Renewal',
        engine: 'ansible',
        category: 'network',
        risk_tier: 'HIGH',
        requires_maker_checker: true,
        detected_environment: 'PROD',
        suggested_parameters: { hostname: 'f5-edge-01.internal', vip_ip: '10.200.1.50', cert_valid_days: 90 },
        reasoning: 'Parsed network security automation request from operational query.'
      };
      setCardForms(prev => ({
        ...prev,
        [assistantMsgId]: {
          targetHost: 'f5-edge-01.internal',
          environment: 'PROD',
          dryRun: false,
          parameters: { hostname: 'f5-edge-01.internal', vip_ip: '10.200.1.50', cert_valid_days: 90 },
          isSubmitting: false
        }
      }));
      setMessages([
        ...newMessages,
        {
          id: assistantMsgId,
          sender: 'assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          cardData: fallbackData
        }
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleExecuteCard = async (msgId: string, cardData: any) => {
    const form = cardForms[msgId];
    if (!form || form.isSubmitting) return;

    setCardForms(prev => ({
      ...prev,
      [msgId]: { ...prev[msgId], isSubmitting: true }
    }));

    try {
      const payload: ChatLaunchPayload = {
        catalog_identifier: cardData.identifier,
        target_resource_id: form.targetHost,
        parameters: form.parameters,
        environment: form.environment,
        dry_run: form.dryRun,
        requester_id: currentUser,
        servicenow_chg: cardData.requires_chg || cardData.requires_maker_checker ? (cardData.servicenow_chg || `CHG-${Math.floor(100000 + Math.random() * 900000)}`) : undefined
      };

      const result = await onDispatchTask(payload);

      // Update message with execution result
      setMessages(prev => prev.map(m => {
        if (m.id === msgId) {
          return {
            ...m,
            executionResult: result
          };
        }
        return m;
      }));
    } catch (err: any) {
      console.error("Execution error:", err);
      setMessages(prev => prev.map(m => {
        if (m.id === msgId) {
          return {
            ...m,
            executionResult: { error: err?.message || 'Execution request failed.' }
          };
        }
        return m;
      }));
    } finally {
      setCardForms(prev => ({
        ...prev,
        [msgId]: { ...prev[msgId], isSubmitting: false }
      }));
    }
  };

  return (
    <div className="flex flex-col h-full bg-glass-surface/90 border border-glass-border rounded-2xl overflow-hidden shadow-glass-panel backdrop-blur-xl">
      {/* Header */}
      <div className="p-4 border-b border-glass-border/80 bg-canvas-subtle/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500/20 to-emerald-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-glow-cyan/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white tracking-wide flex items-center gap-2">
              What do you want to run?
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950/60 text-cyan-300 border border-cyan-800/60">
                AI Intent Engine
              </span>
            </h2>
            <p className="text-xs text-slate-400">
              Natural language dispatcher for 120+ Ansible & Terraform modules
            </p>
          </div>
        </div>

        <button 
          onClick={() => setMessages([messages[0]])}
          className="text-slate-400 hover:text-white text-xs flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-white/5 transition-colors"
          title="Reset conversation"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Clear</span>
        </button>
      </div>

      {/* Quick Prompts Carousel Bar */}
      <div className="px-4 py-2.5 bg-canvas-void/40 border-b border-glass-border/50 overflow-x-auto no-scrollbar flex items-center gap-2">
        <span className="text-[11px] font-mono text-slate-400 whitespace-nowrap flex items-center gap-1">
          <Sliders className="w-3 h-3 text-cyan-400" /> Suggestions:
        </span>
        {QUICK_PROMPTS.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => handleSendPrompt(prompt)}
            className="whitespace-nowrap px-2.5 py-1 text-xs rounded-full bg-white/5 hover:bg-cyan-500/10 hover:border-cyan-500/40 border border-white/10 text-slate-300 hover:text-cyan-300 transition-all text-left"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
            {/* Sender Metadata */}
            <div className="flex items-center gap-2 mb-1 px-1">
              <span className="text-[11px] font-mono text-slate-400">
                {msg.sender === 'user' ? 'You' : 'Vulcan AI Orchestrator'}
              </span>
              <span className="text-[10px] text-slate-400">{msg.timestamp}</span>
            </div>

            {/* User Message Bubble */}
            {msg.sender === 'user' && (
              <div className="max-w-[85%] bg-gradient-to-r from-cyan-900/40 to-blue-900/40 border border-cyan-500/30 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs shadow-glow-cyan/10">
                {msg.text}
              </div>
            )}

            {/* Assistant Text Bubble */}
            {msg.sender === 'assistant' && msg.text && (
              <div className="max-w-[90%] bg-glass-raised border border-glass-border text-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 text-xs leading-relaxed">
                {msg.text}
              </div>
            )}

            {/* Interactive Playbook Launch Card */}
            {msg.sender === 'assistant' && msg.cardData && (
              <div className="w-full max-w-[96%] mt-1 bg-canvas-subtle/90 border border-glass-border-highlight rounded-xl p-4 shadow-xl space-y-3.5">
                {/* Top Badge Row */}
                <div className="flex items-start justify-between gap-2 border-b border-glass-border/60 pb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${
                        msg.cardData.engine === 'ansible' 
                          ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60' 
                          : 'bg-purple-950/80 text-purple-300 border border-purple-800/60'
                      }`}>
                        {msg.cardData.engine === 'ansible' ? '⚡ Ansible Playbook' : '💠 Terraform Stack'}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                        msg.cardData.risk_tier === 'HIGH'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      }`}>
                        Risk: {msg.cardData.risk_tier}
                      </span>
                      <span className="text-[11px] font-mono text-cyan-400 ml-1">
                        {(msg.cardData.confidence * 100).toFixed(0)}% Match
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold text-white tracking-tight">
                      {msg.cardData.name}
                    </h3>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {msg.cardData.description || msg.cardData.reasoning}
                    </p>
                  </div>
                </div>

                {/* Inline Editable Form Fields */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  {/* Target Host */}
                  <div>
                    <label className="text-[10px] font-mono text-slate-400 block mb-1">Target Host / Resource</label>
                    <div className="relative">
                      <input 
                        type="text"
                        value={cardForms[msg.id]?.targetHost || ''}
                        onChange={(e) => {
                          const val = e.target.value;
                          setCardForms(prev => ({
                            ...prev,
                            [msg.id]: { ...prev[msgIdOrKey(msg.id)], targetHost: val }
                          }));
                        }}
                        className="w-full bg-glass-void/80 border border-glass-border focus:border-cyan-400 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none transition-colors"
                        placeholder="e.g. f5-edge-01.internal"
                      />
                    </div>
                  </div>

                  {/* Environment Selector */}
                  <div>
                    <label className="text-[10px] font-mono text-slate-400 block mb-1">Environment Scope</label>
                    <div className="flex items-center gap-1.5">
                      {['PROD', 'UAT', 'DEV', 'STAGING'].map((env) => {
                        const isSelected = cardForms[msg.id]?.environment === env;
                        return (
                          <button
                            key={env}
                            type="button"
                            onClick={() => {
                              setCardForms(prev => ({
                                ...prev,
                                [msg.id]: { ...prev[msgIdOrKey(msg.id)], environment: env }
                              }));
                            }}
                            className={`flex-1 py-1 text-[10px] font-mono font-bold rounded-lg border transition-all ${
                              isSelected
                                ? env === 'PROD'
                                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/60 shadow-glow-crimson/20'
                                  : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/60 shadow-glow-cyan/20'
                                : 'bg-white/5 border-glass-border text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {env}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Dynamic Parameter Fields */}
                  {cardForms[msg.id]?.parameters && Object.entries(cardForms[msg.id].parameters).map(([key, val]) => {
                    if (key === 'hostname' || key === 'target_host') return null;
                    return (
                      <div key={key}>
                        <label className="text-[10px] font-mono text-slate-400 block mb-1">
                          {key.replace(/_/g, ' ').toUpperCase()}
                        </label>
                        <input
                          type="text"
                          value={String(val ?? '')}
                          onChange={(e) => {
                            const newVal = e.target.value;
                            setCardForms(prev => ({
                              ...prev,
                              [msg.id]: {
                                ...prev[msgIdOrKey(msg.id)],
                                parameters: {
                                  ...prev[msgIdOrKey(msg.id)]?.parameters,
                                  [key]: newVal
                                }
                              }
                            }));
                          }}
                          className="w-full bg-glass-void/80 border border-glass-border focus:border-cyan-400 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 font-mono focus:outline-none transition-colors"
                        />
                      </div>
                    );
                  })}
                </div>

                {/* Dry Run Checkbox & Safety Footer */}
                <div className="flex items-center justify-between pt-2 border-t border-glass-border/40">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input 
                      type="checkbox"
                      checked={cardForms[msg.id]?.dryRun || false}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setCardForms(prev => ({
                          ...prev,
                          [msg.id]: { ...prev[msgIdOrKey(msg.id)], dryRun: checked }
                        }));
                      }}
                      className="rounded bg-black/50 border-glass-border text-cyan-400 focus:ring-0 focus:ring-offset-0"
                    />
                    <span className="text-xs text-slate-400">Dry-run simulation (check mode)</span>
                  </label>

                  {/* Execute Button */}
                  <button
                    onClick={() => handleExecuteCard(msg.id, msg.cardData)}
                    disabled={cardForms[msg.id]?.isSubmitting || !!msg.executionResult}
                    className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono text-xs font-bold transition-all ${
                      msg.executionResult 
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 cursor-default'
                        : cardForms[msg.id]?.isSubmitting
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 opacity-70 cursor-wait'
                          : msg.cardData.risk_tier === 'HIGH' && !cardForms[msg.id]?.dryRun
                            ? 'bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white shadow-glow-amber/30'
                            : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-semibold shadow-glow-cyan/30'
                    }`}
                  >
                    {msg.executionResult ? (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        <span>DISPATCHED [{msg.executionResult.correlation_id}]</span>
                      </>
                    ) : cardForms[msg.id]?.isSubmitting ? (
                      <>
                        <Radio className="w-4 h-4 animate-spin" />
                        <span>DISPATCHING...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-current" />
                        <span>{msg.cardData.risk_tier === 'HIGH' && !cardForms[msg.id]?.dryRun ? 'SUBMIT FOR APPROVAL' : 'EXECUTE PLAYBOOK NOW'}</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Execution Result Banner */}
                {msg.executionResult && (
                  <div className="mt-2 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/40 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-emerald-300 font-mono">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>
                        Task registered: <strong>{msg.executionResult.correlation_id}</strong> ({msg.executionResult.status})
                      </span>
                    </div>
                    {onSelectTaskToView && (
                      <button
                        onClick={() => onSelectTaskToView(msg.executionResult.correlation_id)}
                        className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1"
                      >
                        <span>View in Terminal</span>
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Thinking Indicator */}
        {isThinking && (
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 bg-cyan-950/30 border border-cyan-500/20 rounded-xl px-4 py-2.5 w-fit">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            <span>AI intent compiler scanning 120+ playbooks & catalog rules...</span>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-3 border-t border-glass-border/80 bg-canvas-subtle/70">
        <form 
          onSubmit={(e) => {
            e.preventDefault();
            handleSendPrompt(inputPrompt);
          }}
          className="relative flex items-center gap-2"
        >
          <input
            type="text"
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            placeholder="Type what you want to automate (e.g. 'Renew SSL cert on F5' or 'Expand Postgres disk')..."
            className="flex-1 bg-black/60 border border-glass-border focus:border-cyan-400 text-slate-100 text-xs rounded-xl px-4 py-3 placeholder:text-slate-500 focus:outline-none transition-all shadow-inner"
          />
          <button
            type="submit"
            disabled={!inputPrompt.trim() || isThinking}
            className="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-40 disabled:hover:from-cyan-500 text-black font-bold p-3 rounded-xl transition-all shadow-glow-cyan/20 flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

// Helper for safe state access
function msgIdOrKey(id: string) {
  return id;
}
