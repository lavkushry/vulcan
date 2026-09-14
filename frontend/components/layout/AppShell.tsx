'use client';

import { AlertCircle } from 'lucide-react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { CommandPalette } from '@/components/layout/CommandPalette';
import { VulcanProvider, useVulcan } from '@/lib/context';

function ShellInner({ children }: { children: React.ReactNode }) {
  const { currentUser, setCurrentUser, paletteOpen, openPalette, closePalette, authStatus } = useVulcan();

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {authStatus === 'unauthenticated' && (
        <div data-testid="unauthenticated-banner" className="bg-amber-950/80 border-b border-amber-500/30 px-4 py-1.5 text-xs text-amber-200 flex items-center justify-between z-50">
          <div className="flex items-center gap-2">
            <AlertCircle size={13} className="text-amber-400 flex-shrink-0" />
            <span className="font-mono text-[11px] font-medium">
              Unauthenticated Session: Operating in read-only / demo mode.
            </span>
          </div>
          <span className="text-[10px] text-amber-300/80 font-mono hidden sm:inline">
            Select a demo persona or configure VULCAN_API_TOKEN to authenticate
          </span>
        </div>
      )}
      <Header
        currentUser={currentUser}
        onUserChange={setCurrentUser}
        onOpenCommandPalette={openPalette}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-canvas-void">
          {children}
        </main>
      </div>
      <CommandPalette
        open={paletteOpen}
        onClose={closePalette}
        currentUser={currentUser}
      />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <VulcanProvider>
      <ShellInner>{children}</ShellInner>
    </VulcanProvider>
  );
}
