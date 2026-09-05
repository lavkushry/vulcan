'use client';

import { useMemo, useState } from 'react';
import { Circle, MousePointer2, Pencil, Plus, RotateCcw, Wifi, WifiOff } from 'lucide-react';

export type SyncState = 'synced' | 'offline' | 'reconnecting' | 'rejected';
export type WhiteboardElement = { id: string; kind: 'shape' | 'text' | 'sticky'; x: number; y: number; text?: string };

export const benchmarkFixture = {
  elements: Array.from({ length: 10_000 }, (_, index) => ({ id: `fixture-${index}`, kind: 'shape' as const, x: (index % 100) * 24, y: Math.floor(index / 100) * 24 })),
  cursors: Array.from({ length: 50 }, (_, index) => ({ id: `cursor-${index}`, x: index * 8, y: index * 4 })),
};

export default function WhiteboardEditor() {
  const [syncState, setSyncState] = useState<SyncState>('synced');
  const [unsynced, setUnsynced] = useState(0);
  const [elements, setElements] = useState<WhiteboardElement[]>([
    { id: 'welcome', kind: 'text', x: 120, y: 90, text: 'Collaborative board' },
    { id: 'next', kind: 'sticky', x: 280, y: 190, text: 'Add an idea' },
  ]);
  const statusLabel = useMemo(() => ({ synced: 'Synced', offline: 'Offline', reconnecting: 'Reconnecting', rejected: 'Rejected' }[syncState]), [syncState]);

  function addShape() {
    setElements((current) => [...current, { id: `shape-${Date.now()}`, kind: 'shape', x: 180 + current.length * 8, y: 150 }]);
    setUnsynced((count) => count + 1);
  }

  return (
    <section className="flex min-h-[640px] flex-col overflow-hidden rounded-lg border border-slate-700 bg-slate-950 text-slate-100" aria-label="Whiteboard editor">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-4 py-3">
        <div className="flex items-center gap-2"><Circle className="h-3 w-3 fill-cyan-400 text-cyan-400" /><span className="font-semibold">Team board</span></div>
        <div className="flex items-center gap-3 text-xs text-slate-400" aria-live="polite">
          {syncState === 'offline' ? <WifiOff className="h-4 w-4 text-amber-400" /> : <Wifi className="h-4 w-4 text-emerald-400" />}
          <span>{statusLabel}</span><span>{unsynced} unsynced</span>
        </div>
      </header>
      <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-2">
        <button type="button" title="Select" aria-label="Select" className="rounded p-2 text-cyan-300 hover:bg-slate-800"><MousePointer2 className="h-4 w-4" /></button>
        <button type="button" title="Draw" aria-label="Draw" className="rounded p-2 text-slate-300 hover:bg-slate-800"><Pencil className="h-4 w-4" /></button>
        <button type="button" title="Add shape" aria-label="Add shape" onClick={addShape} className="rounded p-2 text-slate-300 hover:bg-slate-800"><Plus className="h-4 w-4" /></button>
        <button type="button" title="Reconnect" aria-label="Reconnect" onClick={() => { setSyncState('reconnecting'); setTimeout(() => setSyncState('synced'), 250); }} className="ml-auto rounded p-2 text-slate-300 hover:bg-slate-800"><RotateCcw className="h-4 w-4" /></button>
      </div>
      <div className="relative flex-1 overflow-auto bg-[linear-gradient(rgba(148,163,184,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,.08)_1px,transparent_1px)] bg-[size:24px_24px]" role="application" aria-label="Canvas">
        {elements.map((element) => <div key={element.id} className={`absolute min-w-24 border p-3 text-sm ${element.kind === 'sticky' ? 'border-amber-300/50 bg-amber-200/90 text-slate-900' : element.kind === 'shape' ? 'border-cyan-300/70 bg-cyan-400/10' : 'border-transparent text-slate-100'}`} style={{ left: element.x, top: element.y }}>{element.text ?? 'Shape'}</div>)}
      </div>
      <footer className="flex items-center justify-between border-t border-slate-800 bg-slate-900 px-4 py-2 text-xs text-slate-400"><span>{elements.length} elements</span><span>50 collaborator cursors ready</span><button type="button" onClick={() => setSyncState('offline')} className="text-slate-300 underline">Simulate offline</button></footer>
    </section>
  );
}
