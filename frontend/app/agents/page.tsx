'use client';

import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { AgentControlCenter } from '@/components/AgentControlCenter';

export default function AgentsPage() {
  return (
    <AppShell>
      <AgentControlCenter />
    </AppShell>
  );
}
