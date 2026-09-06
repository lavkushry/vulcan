'use client';

import React from 'react';
import { X, Command, Keyboard } from 'lucide-react';

export interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const shortcuts = [
    { key: 'j / ↓', description: 'Navigate to next task or row in list' },
    { key: 'k / ↑', description: 'Navigate to previous task or row in list' },
    { key: 'Cmd + Enter', description: 'Authorize pending job or submit prompt' },
    { key: '/', description: 'Focus search or task filter' },
    { key: 'Esc', description: 'Close modal, drawer, or clear filter' },
    { key: '?', description: 'Toggle this keyboard shortcut guide' },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-xl border border-cyan-500/30 bg-[#0C101A] p-5 shadow-[0_0_30px_rgba(0,240,255,0.2)] font-mono text-xs flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2 text-cyan-400 font-bold">
            <Keyboard size={16} />
            <span className="uppercase tracking-wider">Project Vulcan · Hotkey Guide</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        <div className="space-y-2">
          {shortcuts.map((s) => (
            <div
              key={s.key}
              className="flex items-center justify-between p-2 rounded bg-[#07090E] border border-slate-800/80"
            >
              <span className="text-slate-300">{s.description}</span>
              <kbd className="px-2 py-1 rounded bg-slate-900 border border-slate-700 text-cyan-300 text-[11px] font-bold shadow-sm">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500">
          <span>Linear / Vim Ergonomic Standard</span>
          <span>Press <kbd className="text-slate-400">Esc</kbd> to dismiss</span>
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcutsModal;
