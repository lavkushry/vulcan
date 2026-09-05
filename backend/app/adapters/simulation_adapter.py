"""
Project Vulcan: High-Fidelity Simulation Execution Engine Adapter
Author: Alex Xu & Uncle Bob
Simulates Ansible and Terraform executions with realistic stdout streaming, ANSI colors, and health probe hooks.
"""
import time
from typing import Callable, Dict, Optional

from app.domain.entities import EngineExecutionResult, ExecutionJob
from app.ports.interfaces import IExecutionEngine


class SimulationExecutionEngine(IExecutionEngine):
    """
    High-fidelity local execution simulator.
    Emits real-time ANSI terminal events via event_callback for WebSocket streaming.
    """

    def __init__(self, delay_per_step: float = 0.0, force_failure: bool = False):
        self.delay_per_step = delay_per_step
        self.force_failure = force_failure

    def execute(
        self,
        job: ExecutionJob,
        event_callback: Callable[[str], None],
        secrets: Dict[str, str]
    ) -> EngineExecutionResult:
        identifier = job.catalog_item.identifier
        target = job.target_resource_id

        event_callback(f"\033[1;36m[PROJECT VULCAN RUNNER]\033[0m Initializing runtime sandbox for {identifier}...")
        event_callback(f"\033[34m[PAM]\033[0m Ephemeral SSH credentials bound to {secrets.get('TARGET_HOST', target)} in /dev/shm.")

        if self.delay_per_step > 0:
            time.sleep(self.delay_per_step)

        if identifier == "net-f5-cert-renew" or "f5" in identifier:
            steps = [
                "PLAY [Renew SSL/TLS Certificate on F5 BIG-IP VIP] *****************************",
                "TASK [Gathering Facts] *********************************************************",
                f"ok: [{target}]",
                "TASK [f5_vip_update : Validate existing SSL Certificate Expiration] ************",
                f"ok: [{target}] => {{\"cert_cn\": \"{job.parameters.get('hostname', 'vip.pnc.com')}\", \"status\": \"EXPIRING_SOON\"}}",
                "TASK [f5_vip_update : Generate 4096-bit RSA Private Key and CSR] **************",
                f"changed: [{target}] => {{\"algorithm\": \"RSA-4096\", \"key_generated\": true}}",
                "TASK [f5_vip_update : Submit CSR to PNC Internal Automated CA] *****************",
                f"ok: [{target}] => {{\"ca_response\": \"ISSUED\", \"valid_days\": {job.parameters.get('cert_valid_days', 90)}}}",
                "TASK [f5_vip_update : Bind New TLS Certificate to SSL Client Profile] **********",
                f"changed: [{target}] => {{\"profile\": \"clientssl-pnc-prod\", \"vip\": \"{job.parameters.get('vip_ip', '10.200.1.50')}\"}}",
                "TASK [f5_vip_update : Synchronize Configuration Across Active/Standby Pair] ****",
                f"changed: [{target}] => {{\"sync_status\": \"IN_SYNC\", \"peer\": \"f5-secondary-01\"}}",
                "PLAY RECAP *********************************************************************",
                f"{target}                  : ok=6    changed=3    unreachable=0    failed=0"
            ]
        elif identifier == "db-expand-tablespace" or "db" in identifier:
            steps = [
                "PLAY [Expand Database Tablespace Disk Volume] *********************************",
                "TASK [Gathering Facts] *********************************************************",
                f"ok: [{target}]",
                "TASK [storage : Inspect LVM Volume Group Free Extents] **************************",
                f"ok: [{target}] => {{\"vg_free_gb\": 120, \"vg_name\": \"vg_data\"}}",
                "TASK [storage : Extend Logical Volume for Tablespace] **************************",
                f"changed: [{target}] => {{\"lv_name\": \"lv_tablespace\", \"growth\": \"+{job.parameters.get('expand_gb', 50)}GB\"}}",
                "TASK [storage : Online Filesystem Resize (XFS / EXT4)] *************************",
                f"changed: [{target}] => {{\"filesystem\": \"/u01/app/oracle/oradata\", \"status\": \"RESIZED\"}}",
                "TASK [oracle : Execute ALTER TABLESPACE ADD DATAFILE AUTOEXTEND] **************",
                f"changed: [{target}] => {{\"sqlcode\": 0, \"tablespace\": \"{job.parameters.get('tablespace_name', 'USERS_TS')}\"}}",
                "PLAY RECAP *********************************************************************",
                f"{target}                  : ok=5    changed=3    unreachable=0    failed=0"
            ]
        elif identifier == "cloud-vpc-peering" or "peering" in identifier:
            steps = [
                "[Terraform] Initializing backend and providers...",
                "[Terraform] Provider hashicorp/aws v5.60.0 loaded.",
                f"[Terraform] Refreshing state for target resource: {target}",
                f"[Terraform] Plan: 1 to add, 0 to change, 0 to destroy.",
                f"[Terraform] aws_vpc_peering_connection.peer: Creating... [peer_vpc_id={job.parameters.get('peer_vpc_id', 'vpc-098abc')}]",
                f"[Terraform] aws_vpc_peering_connection.peer: Creation complete after 6s [id=pcx-0123456789abcdef0]",
                f"[Terraform] aws_route.peer_route: Creating... [destination_cidr={job.parameters.get('peer_cidr', '10.50.0.0/16')}]",
                f"[Terraform] aws_route.peer_route: Creation complete after 2s",
                "[Terraform] Apply complete! Resources: 2 added, 0 changed, 0 destroyed."
            ]
        else:
            steps = [
                f"PLAY [Execute Automation for {identifier}] *************************************",
                "TASK [Gathering Facts] *********************************************************",
                f"ok: [{target}]",
                f"TASK [runner : Apply Changes on {target}] **************************************",
                f"changed: [{target}] => {{\"status\": \"OK\"}}",
                "PLAY RECAP *********************************************************************",
                f"{target}                  : ok=2    changed=1    unreachable=0    failed=0"
            ]

        full_stdout = []
        for line in steps:
            event_callback(line)
            full_stdout.append(line)
            if self.delay_per_step > 0:
                time.sleep(self.delay_per_step)

        if self.force_failure or job.parameters.get("force_failure"):
            fail_line = f"\033[1;31mFATAL: [{target}]: FAILED! => {{\"msg\": \"Connection refused on port 443 / SSL handshake failure\"}}\033[0m"
            event_callback(fail_line)
            full_stdout.append(fail_line)
            return EngineExecutionResult(
                status="FAILED",
                exit_code=1,
                stdout="\n".join(full_stdout),
                diagnostics="SSL Handshake failure during VIP binding"
            )

        return EngineExecutionResult(
            status="SUCCESS",
            exit_code=0,
            stdout="\n".join(full_stdout)
        )
