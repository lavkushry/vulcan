"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { IntentResult, Job, ParamSpec } from "@/lib/types";

type Msg =
  | { role: "user"; text: string }
  | { role: "assistant"; kind: "info" | "error"; text: string }
  | { role: "assistant"; kind: "intent"; result: IntentResult }
  | { role: "assistant"; kind: "job"; job: Job };

export function ChatPanel({ currentUser, onJobCreated }: {
  currentUser: string;
  onJobCreated: (job: Job) => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([{
    role: "assistant", kind: "info",
    text: "Vulcan assistant online. Describe the change you want to run — e.g. “renew ssl cert on f5-edge-01.pnc.com in prod for 90 days”.",
  }]);
  const [draft, setDraft] = useState<IntentResult | null>(null);   // active intent awaiting submit
  const [values, setValues] = useState<Record<string, string>>({});
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const push = (m: Msg) => setMessages((prev) => [...prev, m]);

  async function send(text?: string) {
    const t = (text ?? input).trim();
    if (!t || busy) return;
    setInput(""); setDraft(null); setValues({});
    push({ role: "user", text: t });
    setBusy(true);
    try {
      const result = await api.resolveIntent(t);
      push({ role: "assistant", kind: "intent", result });
      if (result.status !== "REJECTED" && result.match) {
        setDraft(result);
        setValues(Object.fromEntries(
          Object.entries(result.parameters ?? {}).map(([k, v]) => [k, String(v)]),
        ));
      }
    } catch (e) {
      push({ role: "assistant", kind: "error", text: (e as Error).message });
    } finally { setBusy(false); }
  }

  async function submitRun() {
    if (!draft?.match) return;
    setBusy(true);
    try {
      const job = await api.createJob({
        identifier: draft.match.identifier,
        parameters: values,
        requester_id: currentUser,
        servicenow_chg: draft.servicenow_chg ?? null,
      });
      push({ role: "assistant", kind: "job", job });
      setDraft(null);
      onJobCreated(job);
    } catch (e) {
      push({ role: "assistant", kind: "error", text: (e as Error).message });
    } finally { setBusy(false); }
  }

  const requiredFilled = draft?.match?.params
    .filter((p) => p.required)
    .every((p) => (values[p.name] ?? "").trim() !== "") ?? false;

  return (
    <section className="flex h-full min-h-0 w-full flex-col border-r border-slate-800/80 bg-[#0A0E16]">
      <header className="border-b border-slate-800/80 px-4 py-3">
        <h2 className="text-sm font-semibold tracking-wide text-slate-200">Assistant</h2>
        <p className="text-xs text-slate-500">Describe the change. Nothing executes without validation &amp; approval.</p>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <Bubble key={i} m={m} onResend={(t) => send(t)} />
        ))}
        {busy && <div className="text-xs text-slate-500">…</div>}
      </div>

      {draft?.match && (
        <div className="space-y-3 border-t border-slate-800/80 bg-[#0C101A] p-4">
          <div className="text-xs font-medium text-slate-300">
            {draft.status === "READY" ? "Ready to run — review parameters:" : "Missing parameters — fill the slots:"}
          </div>
          {draft.match.params.map((p) => (
            <SlotInput key={p.name} spec={p} value={values[p.name] ?? ""}
              onChange={(v) => setValues((prev) => ({ ...prev, [p.name]: v }))} />
          ))}
          <button onClick={submitRun} disabled={busy || !requiredFilled}
            className="w-full rounded-md bg-cyan-600/90 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-40">
            Submit run {draft.match.requires_maker_checker ? "→ needs checker approval" : "→ runs immediately"}
          </button>
        </div>
      )}

      <form className="flex gap-2 border-t border-slate-800/80 p-3"
        onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. expand /data by 50gb on pnc-db-01 in uat"
          className="flex-1 rounded-md border border-slate-700 bg-[#07090E] px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-cyan-600 focus:outline-none" />
        <button type="submit" disabled={busy}
          className="rounded-md bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40">Send</button>
      </form>
    </section>
  );
}

function SlotInput({ spec, value, onChange }: {
  spec: ParamSpec; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-400">
        {spec.name}{!spec.required && <span className="ml-1 text-slate-600">(optional)</span>}
      </label>
      {spec.type === "enum" && spec.choices ? (
        <div className="flex gap-2">
          {spec.choices.map((c) => (
            <button key={c} type="button" onClick={() => onChange(c)}
              className={`rounded-md border px-3 py-1 text-xs font-medium ${
                value === c ? "border-cyan-500 bg-cyan-500/15 text-cyan-300"
                            : "border-slate-700 text-slate-400 hover:border-slate-500"}`}>
              {c}
            </button>
          ))}
        </div>
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={spec.description}
          className="w-full rounded-md border border-slate-700 bg-[#07090E] px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-cyan-600 focus:outline-none" />
      )}
    </div>
  );
}

function Bubble({ m, onResend }: { m: Msg; onResend: (text: string) => void }) {
  if (m.role === "user")
    return <div className="ml-8 rounded-lg bg-slate-800/70 px-3 py-2 text-sm text-slate-200">{m.text}</div>;
  if (m.kind === "error")
    return <div className="mr-8 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{m.text}</div>;
  if (m.kind === "info")
    return <div className="mr-8 rounded-lg border border-slate-800 bg-[#0C101A] px-3 py-2 text-xs text-slate-400">{m.text}</div>;
  if (m.kind === "job")
    return (
      <div className="mr-8 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
        <span className="font-mono">{m.job.correlation_id}</span> submitted — <span className="font-medium">{m.job.status}</span>
        {m.job.servicenow_chg ? ` · ServiceNow ${m.job.servicenow_chg}` : ""}. Track it in the Task Monitor →
      </div>
    );

  if (m.kind !== "intent") return null;
  const r = m.result;
  if (r.status === "REJECTED")
    return (
      <div className="mr-8 space-y-2 rounded-lg border border-slate-800 bg-[#0C101A] px-3 py-2 text-xs text-slate-400">
        <div>⚠ {r.reason}</div>
        <div className="flex flex-wrap gap-1.5">
          {r.suggestions?.map((s) => (
            <button key={s.identifier} type="button" onClick={() => onResend(s.name)}
              className="rounded-md border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300 hover:border-cyan-600 hover:text-cyan-300">
              {s.name}
            </button>
          ))}
        </div>
      </div>
    );

  const match = r.match!;
  return (
    <div className="mr-8 space-y-2 rounded-lg border border-slate-800 bg-[#0C101A] p-3 text-xs text-slate-300">
      <div className="flex items-center justify-between">
        <span className="font-medium text-slate-100">{match.name}</span>
        <span className="text-slate-500">{Math.round((r.confidence ?? 0) * 100)}% match</span>
      </div>
      <div className="flex flex-wrap gap-1.5 text-[10px]">
        <span className="rounded border border-slate-700 px-1.5 py-0.5 text-slate-400">{match.engine}</span>
        <span className="rounded border border-slate-700 px-1.5 py-0.5 text-slate-400">{match.risk_tier} risk</span>
        {match.requires_maker_checker && (
          <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-amber-300">maker-checker</span>
        )}
      </div>
      <div className="text-slate-500">{match.description}</div>
      {Object.keys(r.parameters ?? {}).length > 0 && (
        <div className="font-mono text-[11px] text-cyan-300/90">
          {Object.entries(r.parameters).map(([k, v]) => `${k}=${v}`).join("  ")}
        </div>
      )}
      {r.status === "NEEDS_INPUT"
        ? <div className="text-amber-400">Needs input: {r.missing_fields.map((f) => f.name).join(", ")}</div>
        : <div className="text-emerald-400">All parameters resolved.</div>}
    </div>
  );
}
