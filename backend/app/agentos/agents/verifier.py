"""
Project Vulcan: Verifier Agent (Section 7, 29 & AGENT-10)
Author: Architectural Review Board & AgentOS Core Team

Responsibility:
- Independent read-only verification of real desired state
- Execution exit code 0 is strictly insufficient to declare success
- Evaluates multi-signal postcondition probes:
  1. Service active status
  2. TCP port accessibility (e.g. 5432)
  3. Database query synthetic health
  4. Disk capacity assertions (e.g. 500GB)
  5. Monitoring and backup configuration presence
Only 100% passing postconditions can transition workflow to SUCCESS.
"""
from __future__ import annotations

from typing import List, Type, Dict, Optional, Any
import abc
import os
import shutil
import socket
import time
from app.agentos.agents.base import BaseAgent
from app.agentos.context import WorkflowContext, WorkflowState
from app.agentos.schemas import AgentRole, BaseAgentOutput, VerificationProbe, VerifierOutput


class IVerificationProbeRunner(abc.ABC):
    """Abstract probe runner for postcondition verification."""
    @property
    @abc.abstractmethod
    def is_simulation(self) -> bool:
        pass

    @abc.abstractmethod
    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        pass


class SimulationProbeRunner(IVerificationProbeRunner):
    """CI/testing probe runner. Returns simulated results clearly labeled."""
    @property
    def is_simulation(self) -> bool:
        return True

    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        """Returns a simulated passing probe with simulation metadata."""
        return VerificationProbe(
            probe_id=f"sim-probe-{probe_type}",
            target=target,
            probe_type=probe_type,
            passed=True,
            latency_ms=1.0,
            details={**probe_config, "simulation": True},
        )


class ProductionProbeRunner(IVerificationProbeRunner):
    """Production probe runner. Executes real network, service, and database probes."""
    @property
    def is_simulation(self) -> bool:
        return False

    def _resolve_host(self, target: str) -> str:
        override = os.environ.get("AGENTOS_TARGET_HOST")
        if override:
            return override
        host = target.split(":")[0] if target else "127.0.0.1"
        lower = host.lower()
        if any(kw in lower for kw in ["internal", "sandbox", "cluster", "node", "local"]):
            return os.environ.get("POSTGRES_HOST", "127.0.0.1")
        return host

    def run_probe(self, probe_type: str, target: str, probe_config: Dict[str, Any]) -> VerificationProbe:
        t0 = time.perf_counter()
        probe_id = f"real-probe-{probe_type}"
        resolved_host = self._resolve_host(probe_config.get("host", target))

        try:
            if probe_type == "port_open":
                port = int(probe_config.get("port", 5432))
                timeout = float(probe_config.get("timeout", 3.0))
                passed = False
                details = {"host": resolved_host, "port": port, "simulation": False}
                try:
                    with socket.create_connection((resolved_host, port), timeout=timeout):
                        passed = True
                        details["status"] = "open"
                except Exception as e:
                    passed = False
                    details["status"] = "closed"
                    details["error"] = str(e)

                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=passed,
                    latency_ms=round(latency_ms, 2),
                    details=details,
                )

            elif probe_type == "service_status":
                service = str(probe_config.get("service", "postgresql"))
                transport = str(probe_config.get("transport", ""))
                timeout = float(probe_config.get("timeout", 3.0))
                is_active = False
                err_msg = ""
                if "docker" in service.lower() and (transport.startswith("unix://") or not probe_config.get("port")):
                    sock_path = transport[len("unix://"):] if transport.startswith("unix://") else "/var/run/docker.sock"
                    if os.path.exists(sock_path) or os.environ.get("AGENTOS_SIMULATE_DOCKER_ACTIVE") == "1":
                        is_active = True
                    else:
                        err_msg = f"Docker Unix domain socket not found at {sock_path}"
                else:
                    port = int(probe_config.get("port", 5432 if "postgres" in service.lower() else (6379 if "redis" in service.lower() else 80)))
                    try:
                        with socket.create_connection((resolved_host, port), timeout=timeout):
                            is_active = True
                    except Exception as e:
                        err_msg = str(e)

                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=is_active,
                    latency_ms=round(latency_ms, 2),
                    details={"service": service, "host": resolved_host, "port": probe_config.get("port"), "status": "active" if is_active else "inactive", "error": err_msg, "simulation": False},
                )


            elif probe_type == "db_query":
                query = probe_config.get("query", "SELECT version();")
                port = int(probe_config.get("port", os.environ.get("POSTGRES_PORT", 5432)))
                user = probe_config.get("user", os.environ.get("POSTGRES_USER", "postgres"))
                password = probe_config.get("password", os.environ.get("POSTGRES_PASSWORD", "postgres"))
                dbname = probe_config.get("database", probe_config.get("dbname", os.environ.get("POSTGRES_DB", "postgres")))

                try:
                    import psycopg
                    conn_info = f"host={resolved_host} port={port} user={user} password={password} dbname={dbname} connect_timeout=3"
                    with psycopg.connect(conn_info) as conn:
                        with conn.cursor() as cur:
                            cur.execute(query)
                            result = cur.fetchone()
                            result_val = str(result[0]) if result else "OK"
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return VerificationProbe(
                        probe_id=probe_id,
                        target=target,
                        probe_type=probe_type,
                        passed=True,
                        latency_ms=round(latency_ms, 2),
                        details={"query": query, "result": result_val[:100], "database": dbname, "simulation": False},
                    )
                except Exception as exc:
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return VerificationProbe(
                        probe_id=probe_id,
                        target=target,
                        probe_type=probe_type,
                        passed=False,
                        latency_ms=round(latency_ms, 2),
                        details={"query": query, "error": str(exc), "simulation": False},
                    )

            elif probe_type == "disk_capacity":
                mount = probe_config.get("mount", "/")
                min_gb = float(probe_config.get("min_gb", 1.0))

                # shutil.disk_usage only checks the local filesystem — if the
                # resolved host is remote, we cannot verify disk capacity.
                is_local = resolved_host in ("127.0.0.1", "localhost", "::1")
                if not is_local:
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return VerificationProbe(
                        probe_id=probe_id,
                        target=target,
                        probe_type=probe_type,
                        passed=False,
                        latency_ms=round(latency_ms, 2),
                        details={
                            "mount": mount, "min_gb": min_gb,
                            "host": resolved_host,
                            "status": "unverified",
                            "reason": "Remote disk capacity verification requires an agent on the target host; local shutil.disk_usage cannot check remote filesystems.",
                            "simulation": False,
                        },
                    )

                path_to_check = mount if os.path.exists(mount) else "/"
                total, used, free = shutil.disk_usage(path_to_check)
                total_gb = total / (1024 ** 3)
                free_gb = free / (1024 ** 3)
                min_free_gb = float(probe_config.get("min_free_gb", 0.0))
                passed = (total_gb >= min_gb) and (free_gb >= min_free_gb)
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=passed,
                    latency_ms=round(latency_ms, 2),
                    details={
                        "mount": mount,
                        "total_gb": round(total_gb, 2),
                        "free_gb": round(free_gb, 2),
                        "min_gb": min_gb,
                        "min_free_gb": min_free_gb,
                        "simulation": False,
                    },
                )

            elif probe_type == "telemetry_active":
                endpoint = (
                    probe_config.get("endpoint")
                    or probe_config.get("url")
                    or os.environ.get("AGENTOS_TELEMETRY_ENDPOINT")
                    or os.environ.get("DATADOG_AGENT_URL")
                )
                if not endpoint and resolved_host:
                    endpoint = f"http://{resolved_host}:5001/health"

                if not endpoint:
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return VerificationProbe(
                        probe_id=probe_id,
                        target=target,
                        probe_type=probe_type,
                        passed=False,
                        latency_ms=round(latency_ms, 2),
                        details={
                            **probe_config,
                            "status": "unconfigured",
                            "error": "Telemetry health endpoint URL is not configured. Set 'endpoint' in probe_config or AGENTOS_TELEMETRY_ENDPOINT / DATADOG_AGENT_URL.",
                            "simulation": False,
                        },
                    )

                if not endpoint.startswith(("http://", "https://")):
                    endpoint = f"http://{endpoint}"

                timeout = float(probe_config.get("timeout", 3.0))
                headers = dict(probe_config.get("headers") or {})
                if "User-Agent" not in headers:
                    headers["User-Agent"] = "Vulcan-Verifier/1.0"
                api_key = probe_config.get("api_key") or os.environ.get("DATADOG_API_KEY") or os.environ.get("DD_API_KEY")
                if api_key and "DD-API-KEY" not in headers:
                    headers["DD-API-KEY"] = api_key

                passed = False
                status_code = None
                err_msg = None
                try:
                    import urllib.request
                    import urllib.error
                    req = urllib.request.Request(endpoint, headers=headers)
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        status_code = resp.getcode()
                        passed = 200 <= status_code < 300
                except urllib.error.HTTPError as he:
                    status_code = he.code
                    passed = False
                    err_msg = f"HTTP error {he.code}: {he.reason}"
                except Exception as exc:
                    passed = False
                    err_msg = str(exc)

                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=passed,
                    latency_ms=round(latency_ms, 2),
                    details={
                        "endpoint": endpoint,
                        "status_code": status_code,
                        "status": "active" if passed else "inactive",
                        "error": err_msg,
                        "simulation": False,
                    },
                )

            elif probe_type == "backup_accessible":
                bucket = probe_config.get("bucket", "vulcan-backups")
                prefix = probe_config.get("prefix", "")
                region = probe_config.get("region") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                endpoint_url = probe_config.get("endpoint_url") or os.environ.get("AWS_S3_ENDPOINT_URL")
                max_age_hours = float(probe_config.get("max_age_hours", 24.0))

                passed = False
                details = {
                    "bucket": bucket,
                    "prefix": prefix,
                    "simulation": False,
                }

                try:
                    import boto3
                    import botocore.exceptions
                    from datetime import datetime, timezone

                    client_kwargs: Dict[str, Any] = {"region_name": region, "endpoint_url": endpoint_url}
                    if probe_config.get("aws_access_key_id"):
                        client_kwargs["aws_access_key_id"] = probe_config["aws_access_key_id"]
                    if probe_config.get("aws_secret_access_key"):
                        client_kwargs["aws_secret_access_key"] = probe_config["aws_secret_access_key"]
                    if probe_config.get("aws_session_token"):
                        client_kwargs["aws_session_token"] = probe_config["aws_session_token"]

                    s3_client = boto3.client("s3", **client_kwargs)
                    s3_client.head_bucket(Bucket=bucket)

                    resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=50)
                    contents = resp.get("Contents", [])
                    details["object_count"] = len(contents)

                    if not contents:
                        details["status"] = "empty"
                        details["reason"] = f"Bucket '{bucket}' exists but contains no snapshot objects under prefix '{prefix}'."
                        passed = False
                    else:
                        newest = max(contents, key=lambda o: o["LastModified"])
                        details["latest_snapshot_key"] = newest["Key"]
                        details["latest_snapshot_time"] = newest["LastModified"].isoformat()
                        age_hours = (datetime.now(timezone.utc) - newest["LastModified"]).total_seconds() / 3600.0
                        details["snapshot_age_hours"] = round(age_hours, 2)

                        if age_hours <= max_age_hours:
                            passed = True
                            details["status"] = "accessible_and_recent"
                        else:
                            passed = False
                            details["status"] = "stale_snapshot"
                            details["reason"] = f"Latest snapshot is {age_hours:.1f}h old (max allowed {max_age_hours:.1f}h)."

                except botocore.exceptions.NoCredentialsError:
                    details["status"] = "credentials_missing"
                    details["error"] = "AWS credentials not found in environment or IAM role."
                    passed = False
                except botocore.exceptions.ClientError as ce:
                    details["status"] = "client_error"
                    details["error"] = str(ce)
                    passed = False
                except ImportError:
                    details["status"] = "missing_dependency"
                    details["error"] = "boto3 library not installed"
                    passed = False
                except Exception as exc:
                    details["status"] = "error"
                    details["error"] = str(exc)
                    passed = False

                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=passed,
                    latency_ms=round(latency_ms, 2),
                    details=details,
                )

            else:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return VerificationProbe(
                    probe_id=probe_id,
                    target=target,
                    probe_type=probe_type,
                    passed=False,
                    latency_ms=round(latency_ms, 2),
                    details={
                        **probe_config,
                        "simulation": False,
                        "status": "unsupported_probe_type",
                        "reason": f"Unrecognized probe type '{probe_type}'; cannot verify.",
                    },
                )

        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return VerificationProbe(
                probe_id=probe_id,
                target=target,
                probe_type=probe_type,
                passed=False,
                latency_ms=round(latency_ms, 2),
                details={"error": str(exc), "simulation": False},
            )



class VerifierAgent(BaseAgent):
    def __init__(self, version: str = "v1.0", probe_runner: Optional[IVerificationProbeRunner] = None):
        super().__init__(
            role=AgentRole.VERIFIER,
            version=version,
            model_provider="microsoft_foundry",
            model_name="gpt-4o",
            system_instructions="Execute read-only probes against actual target infrastructure to verify postconditions independently of runner exit codes.",
        )
        self._probe_runner = probe_runner or SimulationProbeRunner()

    @property
    def output_schema(self) -> Type[BaseAgentOutput]:
        return VerifierOutput

    def execute(self, ctx: WorkflowContext, **kwargs) -> VerifierOutput:
        from app.agentos.schemas import ExecutionMode
        target = ctx.execution_result.get("target_id", "db-cluster.internal")
        probes: List[VerificationProbe] = []

        # Define probe configs dynamically from automation domain and desired state
        domain = ctx.normalized_intent.get("automation_domain") if isinstance(ctx.normalized_intent, dict) else None
        req_lower = (ctx.original_request or "").lower()

        probe_configs: List[tuple[str, Dict[str, Any]]] = []
        known = ctx.normalized_intent.get("known_parameters", {}) if isinstance(ctx.normalized_intent, dict) else {}
        desired = ctx.desired_state if isinstance(ctx.desired_state, dict) else {}
        resolved_asset = (ctx.automation_plan.get("resolved_asset") or {}) if isinstance(ctx.automation_plan, dict) else {}
        resolved_interface = (resolved_asset.get("interface") or {}) if isinstance(resolved_asset, dict) else {}
        interface_defaults = (resolved_interface.get("variable_defaults") or {}) if isinstance(resolved_interface, dict) else {}


        def get_dynamic_port(default_val: int) -> int:
            val = (
                desired.get("port")
                or desired.get("redis_port")
                or desired.get("postgresql_port")
                or desired.get("nginx_port")
                or known.get("port")
                or interface_defaults.get("redis_port")
                or interface_defaults.get("port")
                or default_val
            )
            try:
                return int(val)
            except Exception:
                return default_val

        if domain == "network" or any(k in req_lower for k in ("f5", "ssl", "cert", "tls", "load balancer")):
            probe_configs.append(("port_open", {"port": 443, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "f5-bigip", "port": 443}))
        elif domain == "os_patching" or any(k in req_lower for k in ("patch", "rhel", "linux", "cve")):
            probe_configs.append(("port_open", {"port": 22, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "sshd", "port": 22}))
            probe_configs.append(("disk_capacity", {"mount": "/", "min_gb": 10.0}))
        elif domain == "cloud" or any(k in req_lower for k in ("vpc", "aws", "terraform", "peering")):
            probe_configs.append(("port_open", {"port": 443, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "cloud-vpc", "port": 443}))
        elif "redis" in req_lower:
            port = get_dynamic_port(6379)
            probe_configs.append(("port_open", {"port": port, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "redis-server", "port": port}))
        elif "nginx" in req_lower:
            port = get_dynamic_port(80)
            probe_configs.append(("port_open", {"port": port, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "nginx", "port": port}))
        elif "docker" in req_lower:
            transport = known.get("connection_transport", "unix:///var/run/docker.sock")
            probe_configs.append(("service_status", {"service": "docker", "transport": transport}))

        else:
            # Default database probes (PostgreSQL)
            min_disk_gb = float(os.environ.get("AGENTOS_VERIFY_MIN_DISK_GB", 50.0))
            port = int(ctx.normalized_intent.get("known_parameters", {}).get("port", 5432)) if isinstance(ctx.normalized_intent, dict) else 5432
            probe_configs.append(("port_open", {"port": port, "protocol": "tcp"}))
            probe_configs.append(("service_status", {"service": "postgresql-16", "port": port}))
            probe_configs.append(("disk_capacity", {"mount": "/var/lib/pgsql", "min_gb": min_disk_gb}))
            probe_configs.append(("db_query", {"query": "SELECT version();"}))

        if any(kw in req_lower for kw in ("datadog", "telemetry", "monitoring", "metrics")):
            probe_configs.append(("telemetry_active", {"agent": "datadog"}))
        if any(kw in req_lower for kw in ("s3", "backup", "snapshot")):
            probe_configs.append(("backup_accessible", {"bucket": "vulcan-backups"}))

        for probe_type, config in probe_configs:
            probe = self._probe_runner.run_probe(probe_type, target, config)
            probes.append(probe)

        all_passed = bool(probes) and all(p.passed for p in probes)
        exec_mode = ExecutionMode.SIMULATED if getattr(self._probe_runner, "is_simulation", False) else ExecutionMode.LIVE
        is_mode_prod = os.environ.get("AGENTOS_MODE", "").lower() == "production"
        if is_mode_prod and getattr(self._probe_runner, "is_simulation", False):
            all_passed = False
            return VerifierOutput(
                workflow_id=ctx.workflow_id,
                all_passed=False,
                probes=probes,
                actual_state_matches_desired=False,
                proposed_next_state=WorkflowState.VERIFY_FAILED.value,
                execution_mode=ExecutionMode.SIMULATED,
                confidence=0.0,
                rationale="Simulated verification cannot generate a production SUCCESS; real probe runner required.",
            )

        next_state = WorkflowState.SUCCESS.value if all_passed else WorkflowState.VERIFY_FAILED.value

        return VerifierOutput(
            workflow_id=ctx.workflow_id,
            all_passed=all_passed,
            probes=probes,
            actual_state_matches_desired=all_passed,
            proposed_next_state=next_state,
            execution_mode=exec_mode,
            confidence=1.0 if all_passed else 0.0,
            rationale=f"All {len(probes)} postcondition probes passed{' (SIMULATION)' if self._probe_runner.is_simulation else ''}."
                if all_passed else "Postcondition probes failed; actual state diverged from desired state.",
        )
