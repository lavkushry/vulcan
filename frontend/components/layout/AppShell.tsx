'use client';

import React from 'react';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { CommandPalette } from '@/components/layout/CommandPalette';
import { VulcanProvider, useVulcan } from '@/lib/context';

function ShellInner({ children }: { children: React.ReactNode }) {
  const { currentUser, setCurrentUser, paletteOpen, openPalette, closePalette } = useVulcan();

  return (
    <div className="flex flex-col h-screen overflow-hidden">
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
