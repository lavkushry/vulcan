"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Job, JobStatus } from "@/lib/types";

export function useJobs(pollMs = 2500) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statusFilter, setStatusFilter] = useState<JobStatus | "ALL">("ALL");
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    try { setJobs(await api.listJobs()); } catch { /* backend down — keep last state */ }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, pollMs);
    return () => clearInterval(t);
  }, [refresh, pollMs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((j) => {
      if (statusFilter !== "ALL" && j.status !== statusFilter) return false;
      if (!q) return true;
      return `${j.correlation_id} ${j.identifier} ${j.name} ${j.servicenow_chg ?? ""}`.toLowerCase().includes(q);
    });
  }, [jobs, statusFilter, query]);

  return { jobs, filtered, statusFilter, setStatusFilter, query, setQuery, refresh };
}
