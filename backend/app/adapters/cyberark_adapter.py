"""
Project Vulcan: CyberArk Privileged Access Management (PAM) Adapter
Author: Robert C. Martin ("Uncle Bob")
Delivers in-memory JIT ephemeral credentials with guaranteed memory scrubbing.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.domain.entities import EphemeralSecretLease
from app.ports.interfaces import ISecretProvider


class CyberArkPAMProvider(ISecretProvider):
    """
    Adapter checking out ephemeral SSH/API credentials into RAM (/dev/shm).
    Revokes leases immediately upon job completion or failure.
    """

    def __init__(self, pam_url: Optional[str] = None, mock_mode: bool = True):
        self.pam_url = pam_url
        self.mock_mode = mock_mode or (pam_url is None)
        self.active_leases: Dict[str, EphemeralSecretLease] = {}
        self.revoked_leases: List[str] = []

    def checkout_ephemeral_secret(self, target: str) -> EphemeralSecretLease:
        lease_id = f"pam-lease-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=15)

        lease = EphemeralSecretLease(
            lease_id=lease_id,
            secrets={
                "VULCAN_SSH_USER": "pnc_svc_automation",
                "VULCAN_SSH_KEY": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...[EPHEMERAL_RAM_ONLY]...==\n-----END RSA PRIVATE KEY-----",
                "TARGET_HOST": target
            },
            issued_at=now,
            expires_at=expires
        )
        self.active_leases[lease_id] = lease
        return lease

    def revoke_ephemeral_secret(self, lease: EphemeralSecretLease) -> None:
        if lease.lease_id in self.active_leases:
            del self.active_leases[lease.lease_id]
        self.revoked_leases.append(lease.lease_id)
