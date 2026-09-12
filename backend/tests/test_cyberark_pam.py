"""
Project Vulcan: CyberArk PAM JIT Secrets Adapter Test Suite (BKND-19)
Author: Robert C. Martin ("Uncle Bob") & Alex Xu
Verifies Central Credential Provider (CCP) REST contracts, volatile RAM-only lifecycle,
deterministic memory zeroization, and guaranteed teardown in BaseJobRunner.
"""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests

from app.adapters.cyberark_adapter import CyberArkPAMProvider
from app.domain.entities import (
    CatalogItem,
    EngineExecutionResult,
    ExecutionEngineType,
    ExecutionJob,
    JobStatus,
    RiskTier,
)
from app.domain.exceptions import SecretResolutionError
from app.use_cases.runner import AnsibleJobRunner


class TestCyberArkPAMProvider(unittest.TestCase):
    """Exhaustive tests for BKND-19 CyberArk Central Credential Provider adapter."""

    def setUp(self):
        self.provider = CyberArkPAMProvider(mock_mode=True)
        self.catalog_item = CatalogItem(
            id="cat-ssh-test",
            identifier="infra-ssh-key-rotate",
            name="Rotate Infrastructure SSH Keys",
            engine=ExecutionEngineType.ANSIBLE,
            git_repo="https://github.pnc.com/vulcan/security-playbooks.git",
            git_commit_sha="b" * 40,
            playbook_or_module_path="playbooks/rotate_keys.yml",
            risk_tier=RiskTier.LOW,
            requires_maker_checker=False,
            requires_chg=False,
            input_schema={
                "properties": {
                    "target_host": {"type": "string"}
                },
                "required": ["target_host"]
            }
        )

    def test_mock_mode_ephemeral_checkout_and_revoke(self):
        """Validates JIT in-memory lease checkout, metadata, and revocation."""
        target = "f5-edge-01.pnc.com"
        lease = self.provider.checkout_ephemeral_secret(target)

        self.assertTrue(lease.lease_id.startswith("pam-lease-"))
        self.assertEqual(lease.secrets["TARGET_HOST"], target)
        self.assertEqual(lease.secrets["VULCAN_SSH_USER"], "pnc_svc_automation")
        self.assertIn("EPHEMERAL_RAM_ONLY", lease.secrets["VULCAN_SSH_KEY"])
        self.assertIn(lease.lease_id, self.provider.active_leases)

        # Revocation
        self.provider.revoke_ephemeral_secret(lease)
        self.assertNotIn(lease.lease_id, self.provider.active_leases)
        self.assertIn(lease.lease_id, self.provider.revoked_leases)

        # Deterministic Memory Zeroization
        self.assertEqual(len(lease.secrets), 0, "Secrets dictionary must be zeroized in-place upon revocation")

    def test_ephemeral_scope_context_manager(self):
        """Validates auto-cleanup when using the ephemeral_scope context manager."""
        target = "db-primary-01.internal"
        lease_id = None
        with self.provider.ephemeral_scope(target) as lease:
            lease_id = lease.lease_id
            self.assertIn(lease_id, self.provider.active_leases)
            self.assertEqual(lease.secrets["TARGET_HOST"], target)

        # Out of scope: must be revoked and wiped
        self.assertNotIn(lease_id, self.provider.active_leases)
        self.assertIn(lease_id, self.provider.revoked_leases)

    def test_emergency_wipe_scrubs_all_active_leases(self):
        """Validates emergency RAM scrubber cleans all active leases on process exit/signal."""
        l1 = self.provider.checkout_ephemeral_secret("target-1")
        l2 = self.provider.checkout_ephemeral_secret("target-2")
        l3 = self.provider.checkout_ephemeral_secret("target-3")

        self.assertEqual(len(self.provider.active_leases), 3)

        wiped_count = self.provider.emergency_wipe()
        self.assertEqual(wiped_count, 3)
        self.assertEqual(len(self.provider.active_leases), 0)
        self.assertEqual(len(l1.secrets), 0)
        self.assertEqual(len(l2.secrets), 0)
        self.assertEqual(len(l3.secrets), 0)

    @patch("requests.get")
    def test_ccp_rest_client_successful_checkout(self, mock_get):
        """Validates Central Credential Provider (CCP) REST query, params, and response parsing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "UserName": "svc_ansible_operator",
            "Content": "-----BEGIN OPENSSH PRIVATE KEY-----\nMIIBOgIBAAJBAK...==\n-----END OPENSSH PRIVATE KEY-----",
            "Address": "vip-east-01.pnc.com"
        }
        mock_get.return_value = mock_response

        live_provider = CyberArkPAMProvider(
            pam_url="https://cyberark-ccp.pnc.com/AIMWebService/api/Accounts",
            app_id="VULCAN_AUTOMATION",
            safe="PNC_PROD_KEYS",
            cert_path="/etc/ssl/certs/vulcan.crt",
            key_path="/etc/ssl/certs/vulcan.key",
            mock_mode=False
        )

        lease = live_provider.checkout_ephemeral_secret("vip-east-01.pnc.com", account_name="PNC_F5_KEY")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://cyberark-ccp.pnc.com/AIMWebService/api/Accounts")
        self.assertEqual(call_args[1]["params"]["AppID"], "VULCAN_AUTOMATION")
        self.assertEqual(call_args[1]["params"]["Safe"], "PNC_PROD_KEYS")
        self.assertEqual(call_args[1]["params"]["Object"], "PNC_F5_KEY")
        self.assertEqual(call_args[1]["cert"], ("/etc/ssl/certs/vulcan.crt", "/etc/ssl/certs/vulcan.key"))

        # Check returned credentials in RAM
        self.assertEqual(lease.secrets["VULCAN_SSH_USER"], "svc_ansible_operator")
        self.assertEqual(lease.secrets["TARGET_HOST"], "vip-east-01.pnc.com")
        self.assertIn("OPENSSH PRIVATE KEY", lease.secrets["VULCAN_SSH_KEY"])

    @patch("requests.get")
    def test_ccp_rest_client_404_account_not_found(self, mock_get):
        """Fails closed with SecretResolutionError when CCP returns HTTP 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Account PNC_UNKNOWN not found in safe"
        mock_get.return_value = mock_response

        live_provider = CyberArkPAMProvider(
            pam_url="https://cyberark-ccp.pnc.com/AIMWebService/api/Accounts",
            mock_mode=False
        )

        with self.assertRaises(SecretResolutionError) as ctx:
            live_provider.checkout_ephemeral_secret("target-404")
        self.assertIn("Account not found", str(ctx.exception))

    @patch("requests.get")
    def test_ccp_rest_client_403_access_denied(self, mock_get):
        """Fails closed with SecretResolutionError when CCP returns HTTP 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Unauthorized AppID"
        mock_get.return_value = mock_response

        live_provider = CyberArkPAMProvider(
            pam_url="https://cyberark-ccp.pnc.com/AIMWebService/api/Accounts",
            mock_mode=False
        )

        with self.assertRaises(SecretResolutionError) as ctx:
            live_provider.checkout_ephemeral_secret("target-403")
        self.assertIn("Access Denied", str(ctx.exception))

    @patch("requests.get")
    def test_ccp_rest_client_timeout_fails_closed(self, mock_get):
        """Fails closed without leaking partial credentials when network times out."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out after 5.0s")

        live_provider = CyberArkPAMProvider(
            pam_url="https://cyberark-ccp.pnc.com/AIMWebService/api/Accounts",
            mock_mode=False
        )

        with self.assertRaises(SecretResolutionError) as ctx:
            live_provider.checkout_ephemeral_secret("target-timeout")
        self.assertIn("timed out", str(ctx.exception))
        self.assertEqual(len(live_provider.active_leases), 0)

    def test_base_job_runner_guarantees_revocation_on_success(self):
        """Validates BaseJobRunner unconditionally revokes and wipes lease on successful run."""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_audit = MagicMock()

        mock_engine = MagicMock()
        mock_engine.execute.return_value = EngineExecutionResult(status="SUCCESS", exit_code=0, stdout="Success")

        runner = AnsibleJobRunner(
            engine_port=mock_engine,
            lock_manager=mock_lock,
            audit_logger=mock_audit,
            secret_provider=self.provider
        )

        job = ExecutionJob(
            job_id="job-runner-success",
            correlation_id="EXEC-RUN-OK",
            catalog_item=self.catalog_item,
            requester_id="operator.alice",
            target_resource_id="vip-node-01.pnc.com",
            parameters={"target_host": "vip-node-01.pnc.com"}
        )
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Queued")

        self.assertEqual(len(self.provider.active_leases), 0)
        res = runner.run(job)
        self.assertEqual(res.status, "SUCCESS")
        self.assertEqual(job.status, JobStatus.SUCCESS)

        # After execution completes: lease must be revoked from provider
        self.assertEqual(len(self.provider.active_leases), 0, "No ephemeral secret leases may remain active after execution")
        self.assertEqual(len(self.provider.revoked_leases), 1)

    def test_base_job_runner_guarantees_revocation_on_failure(self):
        """Validates BaseJobRunner unconditionally revokes and wipes lease even if engine crashes."""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_audit = MagicMock()

        mock_engine = MagicMock()
        mock_engine.execute.side_effect = RuntimeError("Fatal SSH connection dropped mid-flight")

        runner = AnsibleJobRunner(
            engine_port=mock_engine,
            lock_manager=mock_lock,
            audit_logger=mock_audit,
            secret_provider=self.provider
        )

        job = ExecutionJob(
            job_id="job-runner-fail",
            correlation_id="EXEC-RUN-FAIL",
            catalog_item=self.catalog_item,
            requester_id="operator.alice",
            target_resource_id="vip-node-02.pnc.com",
            parameters={"target_host": "vip-node-02.pnc.com"}
        )
        job.parse()
        job.transition_to(JobStatus.QUEUED, "Queued")

        self.assertEqual(len(self.provider.active_leases), 0)
        with self.assertRaises(RuntimeError):
            runner.run(job)

        # Guaranteed teardown in finally: lease must be revoked even on error!
        self.assertEqual(len(self.provider.active_leases), 0, "Active leases must be purged even on unhandled execution failure")
        self.assertEqual(len(self.provider.revoked_leases), 1)


if __name__ == "__main__":
    unittest.main()
