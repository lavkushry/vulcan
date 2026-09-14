'use client';

import React, { Suspense } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ExternalResourcesConsole } from '@/components/ExternalResourcesConsole';

export default function IntegrationsAliasPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-center text-slate-500 font-mono text-xs">Loading integrations…</div>}>
        <ExternalResourcesConsole />
      </Suspense>
    </AppShell>
  );
}
