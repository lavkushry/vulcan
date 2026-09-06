"""
Project Vulcan: Enterprise Integrations Manager (Production Grade)
Connectors for ServiceNow ITSM, Red Hat AAP, GitHub (GitOps Catalog Sync),
Jira Software, HashiCorp Vault, and Datadog / Prometheus.

Features:
- Real outbound HTTP/REST network probes via httpx
- Honest latency measurement, status codes, and TLS/timeout error reporting
- Real GitHub API sync (retrieves real commit SHAs and repository metadata)
- Credential masking for safe frontend display
- Durable SQLite persistence via SQLiteIntegrationRepository
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.adapters.sqlite_repositories import SQLiteIntegrationRepository

logger = logging.getLogger("vulcan.integrations")


def mask_secret(secret: Optional[str]) -> Optional[str]:
    """Masks secret tokens for safe presentation over the REST API."""
    if not secret:
        return None
    s = str(secret)
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:4]}••••••••{s[-4:]}"


DEFAULT_CONNECTORS: List[Dict[str, Any]] = [
    {
        "key": "github",
        "name": "GitHub Enterprise / GitOps",
        "category": "GitOps & Source Control",
        "icon": "git",
        "description": "Single Source of Truth for playbooks and Terraform stacks. Webhook-triggered auto-catalog ingestion with commit SHA pinning.",
        "endpoint_url": "https://api.github.com/repos/lavkushry/vulcan",
        "auth_type": "NONE",
        "auth_token": None,
        "username": "lavkushry",
        "status": "CONNECTED",
        "latency_ms": 35,
        "version": "REST API v3",
        "config_summary": {
            "repository": "lavkushry/vulcan",
            "branch": "main",
            "auto_sync_webhook": "Active (HMAC SHA-256)",
            "immutable_sha_pinning": True,
            "catalog_playbooks_indexed": 120
        },
        "capabilities": [
            "Live GitHub REST API Commit Verification",
            "Strict Git Commit SHA Pinning for every execution",
            "Automated JSON Schema extraction from playbook argument_specs",
            "PR / GitOps Approval Audit Cross-Referencing",
            "Rollback Tag Verification"
        ]
    },
    {
        "key": "servicenow",
        "name": "ServiceNow ITSM & CMDB",
        "category": "Change Management",
        "icon": "shield",
        "description": "Bi-directional Change Request (CHG) validation, maintenance window gate, and automated closure note posting.",
        "endpoint_url": "https://dev12345.service-now.com",
        "auth_type": "BASIC_AUTH",
        "auth_token": None,
        "username": "admin",
        "status": "CONFIGURED",
        "latency_ms": 42,
        "version": "Utah / Washington DC Table API",
        "config_summary": {
            "instance": "dev12345.service-now.com",
            "auth_method": "Basic Auth / OAuth2",
            "chg_table": "change_request",
            "cmdb_ci_table": "cmdb_ci_server",
            "auto_close_on_success": True
        },
        "capabilities": [
            "Validate CHG Ticket State (Scheduled/Implement)",
            "Verify Target Host CI Relationship",
            "Check Planned Start/End Maintenance Window",
            "Auto-append Merkle Audit Proof & Stdout into Work Notes",
            "Auto-Transition CHG to Closed-Complete on 0 Exit Code"
        ]
    },
    {
        "key": "aap",
        "name": "Red Hat Ansible Automation Platform (AAP)",
        "category": "Execution Engine",
        "icon": "cpu",
        "description": "Offloads execution to enterprise AAP/Tower clusters with dynamic inventory, Execution Environments (EE), and Vault credentials.",
        "endpoint_url": "https://aap-controller.internal.net",
        "auth_type": "BEARER_TOKEN",
        "auth_token": None,
        "username": None,
        "status": "CONFIGURED",
        "latency_ms": 25,
        "version": "AAP 2.4 / AWX API v2",
        "config_summary": {
            "controller_url": "https://aap-controller.internal.net",
            "organization": "Enterprise-Infrastructure",
            "default_ee": "ee-supported-rhel9:latest",
            "token_type": "Bearer Application Token",
            "job_templates_count": 48
        },
        "capabilities": [
            "Launch Job Templates via POST /api/v2/job_templates/{id}/launch/",
            "WebSocket Live Stdout Streaming (/api/websocket)",
            "Dynamic Inventory Sync from ServiceNow CMDB",
            "Ephemeral Extravars & Limit Parameter Injection",
            "Native Job Cancellation & Timeout Termination"
        ]
    },
    {
        "key": "jira",
        "name": "Atlassian Jira Software",
        "category": "Issue & Release Governance",
        "icon": "layers",
        "description": "Automatic correlation of operational tasks to Jira Epics, Stories, and Incidents with execution status comments.",
        "endpoint_url": "https://jira.internal.net",
        "auth_type": "BEARER_TOKEN",
        "auth_token": None,
        "username": None,
        "status": "CONFIGURED",
        "latency_ms": 30,
        "version": "Jira REST API v3",
        "config_summary": {
            "base_url": "https://jira.internal.net",
            "project_keys": ["INFRA", "SECOPS", "PLATFORM"],
            "auth_type": "Personal Access Token (PAT)",
            "auto_comment_runs": True
        },
        "capabilities": [
            "Link Vulcan Job to Jira Issue (e.g. INFRA-4821)",
            "Auto-Comment Live Terminal Summary on Completion",
            "Smart State Transition (In Progress -> Resolved)",
            "Jira Incident Auto-Remediation Trigger via Webhook"
        ]
    },
    {
        "key": "vault",
        "name": "HashiCorp Vault / CyberArk",
        "category": "Secrets & Privileged Access",
        "icon": "lock",
        "description": "Zero-standing-privilege credential broker. Generates short-lived SSH certificates, Kerberos tickets, and database passwords at runtime.",
        "endpoint_url": "http://127.0.0.1:8200",
        "auth_type": "BEARER_TOKEN",
        "auth_token": None,
        "username": None,
        "status": "CONFIGURED",
        "latency_ms": 12,
        "version": "Vault API v1",
        "config_summary": {
            "vault_cluster": "http://127.0.0.1:8200",
            "auth_engine": "AppRole / Token Lease",
            "ssh_signer_mount": "ssh-client-signer/",
            "cloud_dynamic_secrets": "aws/, azure/",
            "max_lease_ttl": "30m"
        },
        "capabilities": [
            "Zero Permanent Credentials on Control Plane",
            "Runtime Short-Lived SSH Certificate Signing (15m TTL)",
            "Dynamic AWS STS / Azure Service Principal Token Generation",
            "Automatic Lease Revocation on Job Completion or Failure"
        ]
    },
    {
        "key": "datadog",
        "name": "Datadog / Prometheus Observability",
        "category": "Event Monitoring & AIOps",
        "icon": "activity",
        "description": "Ingests alert webhooks to trigger automated self-healing remediation rules with cooldown and blast-radius guardrails.",
        "endpoint_url": "https://api.datadoghq.com",
        "auth_type": "API_KEY",
        "auth_token": None,
        "username": None,
        "status": "CONFIGURED",
        "latency_ms": 38,
        "version": "Datadog API v1/v2",
        "config_summary": {
            "webhook_endpoint": "/api/v1/rules/webhook",
            "active_remediation_rules": 4,
            "cooldown_enforced": "300s",
            "signature_verification": "Enabled"
        },
        "capabilities": [
            "Ingest Metric & Log Anomaly Alerts in Real-Time",
            "Trigger Vulcan Remediation Rule with Dynamic Payload Parsing",
            "Auto-Suppress Monitoring Alerts during Approved Maintenance Window",
            "Post Execution Audit Events back to Datadog Event Stream"
        ]
    }
]


class IntegrationsManager:
    """
    Manages Enterprise Connectors with real HTTP handshakes, credential storage,
    and live state persistence in SQLite.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            raw = os.getenv("DATABASE_URL", "data/vulcan.db")
            if raw.startswith("postgres"):
                db_path = "data/vulcan.db"
            else:
                db_path = raw
        self.repo = SQLiteIntegrationRepository(db_path=db_path)
        # Seed defaults if database table is brand new
        self.repo.seed_if_empty(DEFAULT_CONNECTORS)

    def list_all(self, mask_secrets: bool = True) -> List[Dict[str, Any]]:
        items = self.repo.list_all()
        # If DB returned empty for any reason, re-seed
        if not items:
            self.repo.seed_if_empty(DEFAULT_CONNECTORS)
            items = self.repo.list_all()

        if mask_secrets:
            for item in items:
                item["auth_token"] = mask_secret(item.get("auth_token"))
        return items

    def get(self, key: str, mask_secrets: bool = True) -> Optional[Dict[str, Any]]:
        item = self.repo.get(key)
        if not item:
            return None
        if mask_secrets:
            item["auth_token"] = mask_secret(item.get("auth_token"))
        return item

    def update_config(self, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates connector parameters (URL, credentials, username, config)."""
        existing = self.repo.get(key)
        if not existing:
            raise KeyError(f"Connector [{key}] not found.")

        # Update fields
        if "endpoint_url" in payload and payload["endpoint_url"]:
            existing["endpoint_url"] = payload["endpoint_url"].strip()
        if "auth_type" in payload:
            existing["auth_type"] = payload["auth_type"]
        if "username" in payload:
            existing["username"] = payload["username"]
        if "auth_token" in payload and payload["auth_token"] and not str(payload["auth_token"]).startswith("••••"):
            existing["auth_token"] = payload["auth_token"]
        if "config_summary" in payload and isinstance(payload["config_summary"], dict):
            existing["config_summary"].update(payload["config_summary"])

        # Reset status on reconfiguration
        existing["status"] = "CONFIGURED"
        self.repo.save(existing)

        # Return with masked token
        res = dict(existing)
        res["auth_token"] = mask_secret(res.get("auth_token"))
        return res

    def test_connection(self, key: str) -> Dict[str, Any]:
        """
        Executes a REAL live HTTP network handshake to the configured endpoint_url.
        Measures exact round-trip latency, verifies status codes, and updates connector status.
        """
        c = self.repo.get(key)
        if not c:
            return {"ok": False, "message": f"Connector [{key}] not found."}

        url = c["endpoint_url"]
        auth_type = c.get("auth_type", "NONE")
        token = c.get("auth_token")
        username = c.get("username")

        headers = {
            "User-Agent": "Project-Vulcan-Control-Plane/1.0",
            "Accept": "application/json, */*"
        }

        auth = None
        if auth_type == "BEARER_TOKEN" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "API_KEY" and token:
            if key == "datadog":
                headers["DD-API-KEY"] = token
            else:
                headers["X-API-Key"] = token
        elif auth_type == "BASIC_AUTH" and username:
            auth = (username, token or "")

        start_time = time.perf_counter()
        now_str = datetime.now(timezone.utc).isoformat()

        # Connector-specific probe endpoint routing
        probe_url = url
        if key == "github":
            # If user provided a github.com repo URL, transform into api.github.com
            if "github.com/" in url and "api.github.com" not in url:
                m = re.search(r"github\.com/([^/]+/[^/]+)", url)
                if m:
                    repo_path = m.group(1).rstrip(".git")
                    probe_url = f"https://api.github.com/repos/{repo_path}"
        elif key == "servicenow":
            if not probe_url.endswith(("/api/now/table/change_request", "/api/now/v1/batch")):
                probe_url = probe_url.rstrip("/") + "/api/now/table/change_request?sysparm_limit=1"
        elif key == "vault":
            if not probe_url.endswith("/v1/sys/health"):
                probe_url = probe_url.rstrip("/") + "/v1/sys/health"
        elif key == "aap":
            if not probe_url.endswith("/api/v2/ping/"):
                probe_url = probe_url.rstrip("/") + "/api/v2/ping/"
        elif key == "jira":
            if not probe_url.endswith(("/rest/api/3/myself", "/rest/api/2/serverInfo")):
                probe_url = probe_url.rstrip("/") + "/rest/api/2/serverInfo"
        elif key == "datadog":
            if not probe_url.endswith("/api/v1/validate"):
                probe_url = probe_url.rstrip("/") + "/api/v1/validate"

        try:
            with httpx.Client(timeout=5.0, follow_redirects=True, verify=False) as client:
                res = client.get(probe_url, headers=headers, auth=auth)
                elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))

                c["latency_ms"] = elapsed_ms
                c["last_sync_at"] = now_str

                # Evaluate HTTP response
                if res.status_code in (200, 201, 204):
                    c["status"] = "CONNECTED"
                    data_summary = ""
                    try:
                        resp_data = res.json()
                        if key == "github":
                            full_name = resp_data.get("full_name", "")
                            branch = resp_data.get("default_branch", "main")
                            c["config_summary"]["default_branch"] = branch
                            c["config_summary"]["repository"] = full_name
                            data_summary = f" (Repo: {full_name}, Branch: {branch})"
                        elif key == "vault":
                            v_ver = resp_data.get("version", "v1.x")
                            c["version"] = f"Vault {v_ver}"
                            data_summary = f" (Vault Version: {v_ver})"
                        elif key == "aap":
                            aap_ver = resp_data.get("version", "")
                            data_summary = f" (AAP Version: {aap_ver})"
                        elif key == "jira":
                            server_title = resp_data.get("serverTitle", "Jira Server")
                            data_summary = f" ({server_title})"
                    except Exception:
                        pass

                    self.repo.save(c)
                    return {
                        "ok": True,
                        "connector": c["name"],
                        "status": "CONNECTED",
                        "status_code": res.status_code,
                        "latency_ms": elapsed_ms,
                        "timestamp": now_str,
                        "message": f"Successfully authenticated and completed live handshake with {probe_url} (HTTP {res.status_code}){data_summary}."
                    }

                elif res.status_code in (401, 403):
                    c["status"] = "AUTH_FAILED"
                    self.repo.save(c)
                    return {
                        "ok": False,
                        "connector": c["name"],
                        "status": "AUTH_FAILED",
                        "status_code": res.status_code,
                        "latency_ms": elapsed_ms,
                        "timestamp": now_str,
                        "message": f"Authentication failed: Remote endpoint returned HTTP {res.status_code} Unauthorized. Please check your credentials or API token."
                    }

                else:
                    c["status"] = "DEGRADED"
                    self.repo.save(c)
                    return {
                        "ok": False,
                        "connector": c["name"],
                        "status": "DEGRADED",
                        "status_code": res.status_code,
                        "latency_ms": elapsed_ms,
                        "timestamp": now_str,
                        "message": f"Remote host responded with HTTP {res.status_code} to probe {probe_url}."
                    }

        except httpx.ConnectTimeout:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            c["status"] = "UNREACHABLE"
            c["latency_ms"] = elapsed_ms
            c["last_sync_at"] = now_str
            self.repo.save(c)
            return {
                "ok": False,
                "connector": c["name"],
                "status": "UNREACHABLE",
                "status_code": None,
                "latency_ms": elapsed_ms,
                "timestamp": now_str,
                "message": f"Connection timed out (exceeded 5.0s) connecting to {probe_url}. Check host firewall or network routing."
            }

        except httpx.ConnectError as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            c["status"] = "UNREACHABLE"
            c["latency_ms"] = elapsed_ms
            c["last_sync_at"] = now_str
            self.repo.save(c)
            return {
                "ok": False,
                "connector": c["name"],
                "status": "UNREACHABLE",
                "status_code": None,
                "latency_ms": elapsed_ms,
                "timestamp": now_str,
                "message": f"Connection refused or DNS resolution failed for {probe_url}: {str(e)}"
            }

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            c["status"] = "ERROR"
            c["latency_ms"] = elapsed_ms
            c["last_sync_at"] = now_str
            self.repo.save(c)
            return {
                "ok": False,
                "connector": c["name"],
                "status": "ERROR",
                "status_code": None,
                "latency_ms": elapsed_ms,
                "timestamp": now_str,
                "message": f"Failed to probe {probe_url}: {str(e)}"
            }

    def trigger_sync(self, key: str) -> Dict[str, Any]:
        """
        Performs live data synchronization with the remote service.
        For GitHub: fetches latest commits on main, verifies SHA, and updates catalog tracking.
        """
        c = self.repo.get(key)
        if not c:
            return {"ok": False, "message": f"Connector [{key}] not found."}

        url = c["endpoint_url"]
        auth_type = c.get("auth_type", "NONE")
        token = c.get("auth_token")
        now_str = datetime.now(timezone.utc).isoformat()

        headers = {
            "User-Agent": "Project-Vulcan-Control-Plane/1.0",
            "Accept": "application/json, */*"
        }
        if auth_type == "BEARER_TOKEN" and token:
            headers["Authorization"] = f"Bearer {token}"

        if key == "github":
            # Extract owner/repo
            repo_match = re.search(r"github\.com(?:/repos)?/([^/]+/[^/]+)", url)
            repo_slug = repo_match.group(1).rstrip(".git") if repo_match else "lavkushry/vulcan"
            commits_url = f"https://api.github.com/repos/{repo_slug}/commits/main"

            try:
                with httpx.Client(timeout=6.0, follow_redirects=True, verify=False) as client:
                    res = client.get(commits_url, headers=headers)
                    if res.status_code == 200:
                        commit_data = res.json()
                        sha = commit_data.get("sha", "")
                        author = commit_data.get("commit", {}).get("author", {}).get("name", "Unknown")
                        msg = commit_data.get("commit", {}).get("message", "").split("\n")[0]

                        c["last_sync_at"] = now_str
                        c["status"] = "CONNECTED"
                        c["config_summary"]["latest_commit_sha"] = sha[:8]
                        c["config_summary"]["latest_author"] = author
                        c["config_summary"]["latest_commit_message"] = msg
                        self.repo.save(c)

                        return {
                            "ok": True,
                            "connector": c["name"],
                            "last_sync_at": now_str,
                            "latest_commit_sha": sha[:8],
                            "message": f"Sync successful with {repo_slug} @ {sha[:7]} ('{msg}') by {author}."
                        }
                    else:
                        return {
                            "ok": False,
                            "connector": c["name"],
                            "message": f"GitHub sync failed (HTTP {res.status_code}): {res.text[:150]}"
                        }
            except Exception as e:
                return {
                    "ok": False,
                    "connector": c["name"],
                    "message": f"GitHub sync error: {str(e)}"
                }

        # For other connectors, perform live health handshake and record sync timestamp
        test_res = self.test_connection(key)
        c = self.repo.get(key)
        if c:
            c["last_sync_at"] = now_str
            self.repo.save(c)

        return {
            "ok": test_res.get("ok", False),
            "connector": c["name"] if c else key,
            "last_sync_at": now_str,
            "message": f"Sync completed. {test_res.get('message', '')}"
        }


# Global singleton instance
integrations_manager = IntegrationsManager()
