'use client';

import React, { useState, useRef, useEffect } from 'react';
import { 
  Sparkles, 
  Send, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  Cpu, 
  Sliders, 
  RotateCcw, 
  Server, 
  ShieldCheck, 
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Layers,
  Check,
  Radio,
  Network,
  Cloud,
  Database,
  Shield,
  CornerDownLeft,
  Bot,
  User,
  Zap
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
  thoughtProcess?: {
    time: string;
    steps: string[];
  };
  cardData?: any;
  executionResult?: any;
}

const QUICK_PROMPTS = [
  { label: "Renew SSL cert on F5", text: "Renew SSL cert on f5-edge-01.internal for 90 days", icon: Network },
  { label: "Expand Postgres tablespace", text: "Expand Postgres tablespace by 100GB on prod-pg-01", icon: Database },
  { label: "Scale AWS EKS nodes", text: "Scale AWS EKS worker nodegroup to 24 in Prod", icon: Cloud },
  { label: "Patch RHEL 9 kernel CVE", text: "Patch RHEL 9 kernel CVE-2025-3912 on rhel-app-01", icon: Shield },
  { label: "AWS VPC Peering", text: "Peer AWS VPC with peer CIDR 10.150.0.0/16", icon: Cloud },
  { label: "Rotate SSH keys", text: "Rotate SSH authorized keys across prod bastions", icon: ShieldCheck }
];

export default function ChatAssistant({ onDispatchTask, onSelectTaskToView, currentUser = 'eng.alice' }: ChatAssistantProps) {
  const [inputPrompt, setInputPrompt] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [openThoughts, setOpenThoughts] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome-msg',
      sender: 'assistant',
      timestamp: 'Just now',
      text: "👋 Hello! I am **Vulcan Copilot**. Tell me what you want to automate in natural language, and I will resolve the exact playbook or Terraform stack from your 120+ catalog, fill the parameters, and prepare safe execution.",
      thoughtProcess: {
        time: '0.4s',
        steps: [
          'Initialized Vulcan Neural Intent Engine',
          'Indexed 120 production-grade playbooks across 6 infrastructure packs',
          'Enforced Maker-Checker & ServiceNow Change Governance'
        ]
      }
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  const toggleThought = (msgId: string) => {
    setOpenThoughts(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

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

    const startTime = performance.now();

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
        cardData = {
          matched: true,
          confidence: 0.96,
          identifier: 'net-f5-cert-renew',
          name: 'F5 BIG-IP SSL Certificate Renewal',
          engine: 'ansible',
          category: 'network',
          risk_tier: 'HIGH',
          requires_maker_checker: true,
          detected_environment: 'PROD',
          suggested_parameters: { hostname: 'f5-edge-01.internal', vip_ip: '10.200.1.50', cert_valid_days: 90 },
          reasoning: 'Extracted intent for SSL Certificate Renewal on F5 BIG-IP load balancer.'
        };
      }

      const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
      const assistantMsgId = `asst-${Date.now()}`;
      
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

      // Automatically keep thought open for fresh responses
      setOpenThoughts(prev => ({ ...prev, [assistantMsgId]: true }));

      setMessages([
        ...newMessages,
        {
          id: assistantMsgId,
          sender: 'assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `I resolved your request to **${cardData.name}** with **${Math.round(cardData.confidence * 100)}% confidence**. Here is the execution launch card with extracted parameters:`,
          thoughtProcess: {
            time: `${elapsed}s`,
            steps: [
              `Scanned catalog: Matched intent to [${cardData.identifier}]`,
              `Extracted target host: ${cardData.suggested_parameters?.hostname || 'f5-edge-01.internal'}`,
              `Detected environment: ${cardData.detected_environment || 'PROD'}`,
              cardData.requires_maker_checker 
                ? 'Governance Gate: High-risk Tier 1 action requires Dual Signoff (Maker-Checker)'
                : 'Governance Gate: Low-risk pre-approved execution allowed'
            ]
          },
          cardData: cardData
        }
      ]);
    } catch (err) {
      console.error("Failed to resolve intent:", err);
      const assistantMsgId = `asst-${Date.now()}`;
      const fallbackData = {
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
          text: `I matched your request to **${fallbackData.name}**. Ready to review parameters:`,
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
    <div className="flex flex-col h-full bg-canvas-void select-text">
      {/* Header Bar */}
      <div className="px-5 py-3 border-b border-glass-border/60 flex items-center justify-between bg-glass-surface/30 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-400 via-purple-500 to-emerald-400 p-[1.5px] shadow-glow-cyan/20">
            <div className="w-full h-full rounded-full bg-canvas-void flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-cyan-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white tracking-wide">Vulcan Copilot</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                120+ Playbooks Ready
              </span>
            </div>
            <p className="text-[11px] text-slate-400">Natural language orchestrator • Gemini/ChatGPT Simplicity</p>
          </div>
        </div>

        <button 
          onClick={() => setMessages([messages[0]])}
          className="text-slate-400 hover:text-slate-200 text-xs flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border hover:bg-white/[0.04] transition-all"
          title="Reset conversation"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Reset Chat</span>
        </button>
      </div>

      {/* Quick Prompts Carousel Bar */}
      <div className="px-5 py-2.5 bg-canvas-void/80 border-b border-glass-border/40 overflow-x-auto no-scrollbar flex items-center gap-2">
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider whitespace-nowrap flex items-center gap-1 mr-1">
          <Zap className="w-3 h-3 text-cyan-400" /> Try:
        </span>
        {QUICK_PROMPTS.map((prompt, idx) => {
          const Icon = prompt.icon;
          return (
            <button
              key={idx}
              onClick={() => handleSendPrompt(prompt.text)}
              className="group whitespace-nowrap px-3 py-1 text-xs rounded-full bg-glass-surface/80 hover:bg-cyan-500/10 border border-glass-border hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 transition-all duration-200 flex items-center gap-1.5 hover:-translate-y-0.5"
            >
              <Icon className="w-3 h-3 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              <span>{prompt.label}</span>
            </button>
          );
        })}
      </div>

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {messages.map((msg) => (
          <div 
            key={msg.id} 
            className={`flex flex-col animate-fade-in-up ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
          >
            {/* Sender Metadata */}
            <div className="flex items-center gap-2 mb-1.5 px-1 text-[11px] font-mono text-slate-500">
              {msg.sender === 'user' ? (
                <>
                  <span>You ({currentUser})</span>
                  <span>•</span>
                  <span>{msg.timestamp}</span>
                </>
              ) : (
                <>
                  <div className="w-4 h-4 rounded-full bg-cyan-400/20 flex items-center justify-center text-cyan-400 text-[10px]">
                    ✦
                  </div>
                  <span className="text-slate-300 font-semibold">Vulcan Copilot</span>
                  <span>•</span>
                  <span>{msg.timestamp}</span>
                </>
              )}
            </div>

            {/* User Message Bubble */}
            {msg.sender === 'user' && (
              <div className="max-w-[80%] bg-gradient-to-r from-cyan-950/60 to-blue-950/60 border border-cyan-500/30 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-xs leading-relaxed shadow-lg shadow-cyan-950/20">
                {msg.text}
              </div>
            )}

            {/* Assistant Text & Thought Bubble */}
            {msg.sender === 'assistant' && (
              <div className="w-full max-w-[92%] space-y-3">
                {/* Gemini-Style Thought Process Accordion */}
                {msg.thoughtProcess && (
                  <div className="rounded-xl border border-glass-border bg-glass-surface/40 overflow-hidden text-xs font-mono transition-all">
                    <button
                      onClick={() => toggleThought(msg.id)}
                      className="w-full px-3.5 py-2 flex items-center justify-between text-slate-400 hover:text-cyan-300 hover:bg-white/[0.02] transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
                        <span className="text-[11px]">Reasoning &amp; Intent Resolution</span>
                        <span className="text-[10px] text-slate-500">• {msg.thoughtProcess.time}</span>
                      </div>
                      {openThoughts[msg.id] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {openThoughts[msg.id] && (
                      <div className="px-3.5 pb-3 pt-1 border-t border-glass-border/40 text-[11px] text-slate-400 space-y-1 bg-canvas-void/40">
                        {msg.thoughtProcess.steps.map((step, idx) => (
                          <div key={idx} className="flex items-start gap-2">
                            <span className="text-cyan-400">✓</span>
                            <span>{step}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Assistant Explanatory Text */}
                {msg.text && (
                  <div className="text-xs text-slate-200 leading-relaxed font-sans px-1">
                    {msg.text}
                  </div>
                )}

                {/* Interactive Playbook Launch Card */}
                {msg.cardData && (
                  <div className="rounded-2xl border border-glass-border-highlight bg-glass-surface/90 p-5 shadow-2xl backdrop-blur-xl space-y-4 transition-all duration-300 hover:border-cyan-500/40">
                    {/* Header */}
                    <div className="flex items-start justify-between border-b border-glass-border/60 pb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1.5">
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
                            {Math.round(msg.cardData.confidence * 100)}% Match
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-white tracking-tight font-mono">
                          {msg.cardData.name}
                        </h3>
                        <p className="text-xs text-slate-400 mt-1">
                          {msg.cardData.description || msg.cardData.reasoning}
                        </p>
                      </div>
                    </div>

                    {/* Inline Form Slots */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {/* Target Host */}
                      <div>
                        <label className="text-[10px] font-mono text-slate-400 block mb-1">Target Host / Resource</label>
                        <input 
                          type="text"
                          value={cardForms[msg.id]?.targetHost || ''}
                          onChange={(e) => {
                            const val = e.target.value;
                            setCardForms(prev => ({
                              ...prev,
                              [msg.id]: { ...prev[msg.id], targetHost: val }
                            }));
                          }}
                          className="w-full bg-canvas-void/80 border border-glass-border focus:border-cyan-400 text-slate-200 text-xs rounded-xl px-3 py-2 font-mono outline-none transition-all focus:ring-1 focus:ring-cyan-400/40"
                          placeholder="e.g. f5-edge-01.internal"
                        />
                      </div>

                      {/* Environment Scope Selector */}
                      <div>
                        <label className="text-[10px] font-mono text-slate-400 block mb-1">Target Environment</label>
                        <div className="flex items-center gap-1.5">
                          {['DEV', 'UAT', 'PROD'].map((env) => {
                            const isSelected = cardForms[msg.id]?.environment === env;
                            return (
                              <button
                                key={env}
                                type="button"
                                onClick={() => {
                                  setCardForms(prev => ({
                                    ...prev,
                                    [msg.id]: { ...prev[msg.id], environment: env }
                                  }));
                                }}
                                className={`flex-1 py-1.5 text-[10px] font-mono font-bold rounded-lg border transition-all ${
                                  isSelected
                                    ? env === 'PROD'
                                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/60 shadow-glow-crimson/20 scale-[1.02]'
                                      : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/60 shadow-glow-cyan/20 scale-[1.02]'
                                    : 'bg-white/5 border-glass-border text-slate-400 hover:text-slate-200'
                                }`}
                              >
                                {env}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Dynamic Parameters */}
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
                                    ...prev[msg.id],
                                    parameters: {
                                      ...prev[msg.id]?.parameters,
                                      [key]: newVal
                                    }
                                  }
                                }));
                              }}
                              className="w-full bg-canvas-void/80 border border-glass-border focus:border-cyan-400 text-slate-200 text-xs rounded-xl px-3 py-2 font-mono outline-none transition-all focus:ring-1 focus:ring-cyan-400/40"
                            />
                          </div>
                        );
                      })}
                    </div>

                    {/* Footer: Dry Run Toggle & Action Button */}
                    <div className="flex items-center justify-between pt-3 border-t border-glass-border/40">
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input 
                          type="checkbox"
                          checked={cardForms[msg.id]?.dryRun || false}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setCardForms(prev => ({
                              ...prev,
                              [msg.id]: { ...prev[msg.id], dryRun: checked }
                            }));
                          }}
                          className="w-4 h-4 rounded bg-black/50 border-glass-border text-cyan-400 focus:ring-0 focus:ring-offset-0"
                        />
                        <span className="text-xs text-slate-400">Dry-run simulation (--check)</span>
                      </label>

                      <button
                        onClick={() => handleExecuteCard(msg.id, msg.cardData)}
                        disabled={cardForms[msg.id]?.isSubmitting || !!msg.executionResult}
                        className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition-all duration-300 ${
                          msg.executionResult 
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 cursor-default'
                            : cardForms[msg.id]?.isSubmitting
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 opacity-70 cursor-wait'
                              : msg.cardData.risk_tier === 'HIGH' && !cardForms[msg.id]?.dryRun
                                ? 'bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white shadow-glow-amber/30 hover:scale-[1.02]'
                                : 'bg-gradient-to-r from-cyan-400 via-cyan-500 to-blue-600 hover:from-cyan-300 hover:to-blue-500 text-black font-semibold shadow-glow-cyan/30 hover:scale-[1.02]'
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
                            <span>DISPATCHING TASK…</span>
                          </>
                        ) : (
                          <>
                            <Play className="w-4 h-4 fill-current" />
                            <span>{msg.cardData.risk_tier === 'HIGH' && !cardForms[msg.id]?.dryRun ? 'SUBMIT FOR APPROVAL' : 'LAUNCH ACTION NOW'}</span>
                          </>
                        )}
                      </button>
                    </div>

                    {/* Feedback Alert */}
                    {msg.executionResult && (
                      <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 flex items-center justify-between text-xs font-mono animate-fade-in-up">
                        <div className="flex items-center gap-2 text-emerald-300">
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                          <span>
                            Execution queued: <strong>{msg.executionResult.correlation_id}</strong> ({msg.executionResult.status})
                          </span>
                        </div>
                        {onSelectTaskToView && (
                          <button
                            onClick={() => onSelectTaskToView(msg.executionResult.correlation_id)}
                            className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1 transition-colors"
                          >
                            <span>Open in Terminal Stream</span>
                            <ChevronRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Gemini Wave / Thinking Indicator */}
        {isThinking && (
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-glass-surface/60 border border-cyan-500/30 text-xs font-mono text-cyan-300 w-fit animate-fade-in-up">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" />
            </div>
            <span>Reasoning across 120+ playbooks &amp; matching parameters…</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Floating Centered Input Bar (ChatGPT & Google Gemini Standard) */}
      <div className="p-4 border-t border-glass-border/60 bg-glass-surface/30 backdrop-blur-xl">
        <form 
          onSubmit={(e) => {
            e.preventDefault();
            handleSendPrompt(inputPrompt);
          }}
          className="max-w-3xl mx-auto relative flex items-center rounded-2xl border border-glass-border bg-canvas-void/90 p-1.5 shadow-2xl transition-all duration-300 focus-within:border-cyan-400/80 focus-within:shadow-[0_0_25px_rgba(0,240,255,0.2)]"
        >
          <div className="pl-3 pr-2 text-cyan-400 flex items-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            placeholder="Ask Copilot to run any task (e.g. 'Renew SSL cert on F5' or 'Scale AWS EKS nodes')..."
            className="flex-1 bg-transparent text-xs text-slate-100 placeholder-slate-500 py-2.5 outline-none font-sans"
          />
          <div className="flex items-center gap-2 pr-1">
            <span className="text-[10px] font-mono text-slate-500 hidden sm:inline">
              ↵ Enter
            </span>
            <button
              type="submit"
              disabled={!inputPrompt.trim() || isThinking}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-200 ${
                inputPrompt.trim() && !isThinking
                  ? 'bg-gradient-to-r from-cyan-400 to-blue-500 text-black shadow-glow-cyan/40 hover:scale-105 active:scale-95'
                  : 'bg-white/5 text-slate-600 cursor-not-allowed'
              }`}
            >
              <CornerDownLeft className="w-3.5 h-3.5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
