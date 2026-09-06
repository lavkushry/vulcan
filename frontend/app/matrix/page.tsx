'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import TaskMatrixTable, { TaskRecord } from '@/components/TaskMatrixTable';
import { useVulcan } from '@/lib/context';
import { api } from '@/lib/api';
import type { Job } from '@/lib/types';
import { useRouter } from 'next/navigation';

function MatrixContent() {
  const { currentUser } = useVulcan();
  const router = useRouter();
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${BASE}/api/v1/tasks`);
      if (res.ok) {
        const data = await res.json();
        const rawTasks = data.tasks || data;
        if (Array.isArray(rawTasks)) {
          setTasks(rawTasks);
          return;
        }
      }
      // Fallback to jobs list mapped to TaskRecord
      const jobs = await api.listJobs(currentUser);
      const mapped: TaskRecord[] = jobs.map((j: Job) => ({
        id: j.id,
        correlation_id: j.correlation_id,
        identifier: j.identifier,
        name: j.name,
        engine: j.engine,
        category: 'cloud',
        target_resource: String((j.parameters as any)?.hostname || (j.parameters as any)?.vpc_id || (j.parameters as any)?.target_host || 'prod-core-01'),
        environment: String((j.parameters as any)?.environment || 'PROD'),
        status: j.status,
        risk_tier: j.risk_tier,
        requester_id: j.requester_id,
        approver_id: j.approver_id,
        duration_sec: j.completed_at ? Math.max(1, Math.round((new Date(j.completed_at).getTime() - new Date(j.created_at).getTime()) / 1000)) : 12,
        created_at: j.created_at,
        parameters: j.parameters,
        servicenow_chg: j.servicenow_chg,
        diagnostic: j.diagnostic,
        capabilities: j.capabilities,
      }));
      setTasks(mapped);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
    const t = setInterval(loadTasks, 4000);
    return () => clearInterval(t);
  }, [loadTasks]);

  const handleOpenTerminal = (task: TaskRecord) => {
    router.push(`/history?selected=${encodeURIComponent(task.correlation_id)}`);
  };

  const handleApprove = async (task: TaskRecord) => {
    try {
      await api.approveJob(task.correlation_id, currentUser);
      await loadTasks();
    } catch (e: any) {
      alert(e?.message || 'Approval failed');
    }
  };

  const handleReject = async (task: TaskRecord) => {
    try {
      await api.rejectJob(task.correlation_id, currentUser);
      await loadTasks();
    } catch (e: any) {
      alert(e?.message || 'Rejection failed');
    }
  };

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex-1 overflow-auto">
        <TaskMatrixTable
          tasks={tasks}
          currentUser={currentUser}
          onOpenTerminal={handleOpenTerminal}
          onApproveTask={handleApprove}
          onRejectTask={handleReject}
          onRefresh={loadTasks}
          isLoading={loading}
        />
      </div>
    </div>
  );
}

export default function MatrixPage() {
  return (
    <AppShell>
      <MatrixContent />
    </AppShell>
  );
}
