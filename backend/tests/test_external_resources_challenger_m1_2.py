"""
Project Vulcan: Milestone 1 Adversarial Challenge Harness (Challenger 2)
Scope:
1. Merkle audit hash chain tampering detection:
   - Demonstrate that mutating any field in payload (top-level, nested, added, removed, types),
     timestamp, action, actor, resource_id, or prev_hash alters the SHA-256 hash and breaks chain verification.
   - Demonstrate avalanche and cascade invalidation across multi-node chains.
   - Verify canonical JSON serialization order independence and Unicode robustness.
2. Concurrency & Immutability:
   - Verify that ExternalResourceVersion, ExternalResourceHealth, and ExternalResourceAuditRecord
     are strictly immutable (dataclasses.FrozenInstanceError upon assignment or delattr).
   - Verify deep-copy isolation in to_dict() outputs.
   - Verify thread-safe concurrent reads on frozen entities and thread-safe serialized mutations.
3. Monotonic revision increments in update_configuration():
   - Verify strict monotonic increment (+1) on valid configuration updates across many iterations.
   - Verify strict atomicity and non-incrementation if config linting or secret_refs validation fails.
   - Verify boundary and type validations on update_configuration().
"""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone, timedelta
import hashlib
import json
import threading
from typing import Any, Dict, List, Optional, Tuple
import pytest

from app.domain.external_resource_entities import (
    AuthMode,
    ExternalResource,
    ExternalResourceAuditRecord,
    ExternalResourceHealth,
    ExternalResourceVersion,
    HealthStatus,
    ResourceCategory,
    ResourceEnvironment,
)
from app.domain.exceptions import ParameterValidationError, SecretLintError


# =====================================================================
# CHAIN VERIFICATION ORACLE
# =====================================================================

def verify_audit_chain(
    records: List[ExternalResourceAuditRecord],
    genesis_prev_hash: str = "0" * 64,
) -> Tuple[bool, Optional[int], str]:
    """
    Oracle that verifies the cryptographic integrity of an audit ledger chain.
    Returns (is_valid, failure_index, failure_reason).
    """
    if not records:
        return True, None, "Empty chain is valid"

    for idx, rec in enumerate(records):
        # 1. Verify prev_hash linkage
        if idx == 0:
            if rec.prev_hash != genesis_prev_hash:
                return False, idx, f"Genesis block prev_hash mismatch: expected {genesis_prev_hash}, got {rec.prev_hash}"
        else:
            prev_rec = records[idx - 1]
            if rec.prev_hash != prev_rec.current_hash:
                return False, idx, f"Broken chain link at index {idx}: rec.prev_hash != prev_rec.current_hash"

        # 2. Recompute and verify current_hash
        expected_hash = ExternalResourceAuditRecord.compute_hash(
            resource_id=rec.resource_id,
            timestamp=rec.timestamp,
            actor=rec.actor,
            action=rec.action,
            payload=rec.payload,
            prev_hash=rec.prev_hash,
        )
        if rec.current_hash != expected_hash:
            return False, idx, f"Hash integrity failure at index {idx}: recorded {rec.current_hash} != computed {expected_hash}"

    return True, None, "Chain is cryptographically valid"


def build_synthetic_chain(
    length: int = 25,
    resource_id: str = "foundry-prod",
    genesis_prev_hash: str = "0" * 64,
) -> List[ExternalResourceAuditRecord]:
    """Builds a valid cryptographic audit chain of specified length."""
    chain: List[ExternalResourceAuditRecord] = []
    prev_hash = genesis_prev_hash
    base_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)

    actions = ["CREATE", "UPDATE", "TEST", "SYNC", "UPDATE"]
    actors = ["admin.dave", "sec.carol", "lead.bob", "system"]

    for i in range(length):
        t_str = (base_time + timedelta(seconds=i * 60)).isoformat()
        action = actions[i % len(actions)]
        actor = actors[i % len(actors)]
        payload = {
            "seq": i,
            "action": action,
            "endpoint": f"https://foundry-prod.services.ai.azure.com/v{i}",
            "params": {"timeout": 30 + i, "retry_policy": {"max_retries": 3, "backoff": "exponential"}},
        }
        curr_hash = ExternalResourceAuditRecord.compute_hash(
            resource_id=resource_id,
            timestamp=t_str,
            actor=actor,
            action=action,
            payload=payload,
            prev_hash=prev_hash,
        )
        rec = ExternalResourceAuditRecord(
            id=i + 1,
            resource_id=resource_id,
            timestamp=t_str,
            actor=actor,
            action=action,
            payload=payload,
            prev_hash=prev_hash,
            current_hash=curr_hash,
        )
        chain.append(rec)
        prev_hash = curr_hash

    return chain


# =====================================================================
# 1. MERKLE AUDIT HASH CHAIN TAMPERING SUITE
# =====================================================================

class TestMerkleAuditTampering:
    """Adversarial stress-testing of Merkle audit hash chain integrity and tampering detection."""

    def test_genuine_chain_verifies_cleanly(self):
        chain = build_synthetic_chain(25)
        assert len(chain) == 25
        valid, failed_idx, msg = verify_audit_chain(chain)
        assert valid is True
        assert failed_idx is None

    @pytest.mark.parametrize(
        "mutation_desc,mutator",
        [
            ("modify_top_level_value", lambda p: {**p, "endpoint": "https://attacker-controlled.site"}),
            ("modify_nested_value", lambda p: {**p, "params": {**p["params"], "timeout": 9999}}),
            ("add_new_key", lambda p: {**p, "unauthorized_flag": True}),
            ("remove_existing_key", lambda p: {k: v for k, v in p.items() if k != "seq"}),
            ("mutate_data_type", lambda p: {**p, "seq": str(p["seq"])}),
            ("flip_boolean", lambda p: {**p, "params": {**p["params"], "retry_policy": {"max_retries": 3, "backoff": 0}}}),
            ("null_injection", lambda p: {**p, "injected_null": None}),
        ],
    )
    def test_tampering_payload_breaks_hash_and_verification(self, mutation_desc, mutator):
        chain = build_synthetic_chain(10)
        target_idx = 4
        orig = chain[target_idx]

        tampered_payload = mutator(orig.payload)
        assert tampered_payload != orig.payload

        # Re-creating the record with the tampered payload but retaining recorded current_hash
        tampered_rec = ExternalResourceAuditRecord(
            id=orig.id,
            resource_id=orig.resource_id,
            timestamp=orig.timestamp,
            actor=orig.actor,
            action=orig.action,
            payload=tampered_payload,
            prev_hash=orig.prev_hash,
            current_hash=orig.current_hash,
        )

        # 1. Verify computed hash differs
        recomputed = ExternalResourceAuditRecord.compute_hash(
            tampered_rec.resource_id,
            tampered_rec.timestamp,
            tampered_rec.actor,
            tampered_rec.action,
            tampered_rec.payload,
            tampered_rec.prev_hash,
        )
        assert recomputed != orig.current_hash, f"Hash collision for mutation: {mutation_desc}"

        # 2. Verify chain verification fails at target_idx
        tampered_chain = list(chain)
        tampered_chain[target_idx] = tampered_rec
        valid, failed_idx, msg = verify_audit_chain(tampered_chain)
        assert valid is False
        assert failed_idx == target_idx
        assert "Hash integrity failure" in msg

    def test_tampering_timestamp_even_by_microsecond_breaks_hash(self):
        chain = build_synthetic_chain(5)
        target_idx = 2
        orig = chain[target_idx]

        # Shift timestamp by 1 millisecond
        dt = datetime.fromisoformat(orig.timestamp)
        altered_dt = dt + timedelta(microseconds=1000)
        altered_ts = altered_dt.isoformat()
        assert altered_ts != orig.timestamp

        new_hash = ExternalResourceAuditRecord.compute_hash(
            orig.resource_id, altered_ts, orig.actor, orig.action, orig.payload, orig.prev_hash
        )
        assert new_hash != orig.current_hash

        tampered_rec = ExternalResourceAuditRecord(
            id=orig.id,
            resource_id=orig.resource_id,
            timestamp=altered_ts,
            actor=orig.actor,
            action=orig.action,
            payload=orig.payload,
            prev_hash=orig.prev_hash,
            current_hash=orig.current_hash,
        )
        chain[target_idx] = tampered_rec
        valid, failed_idx, _ = verify_audit_chain(chain)
        assert valid is False
        assert failed_idx == target_idx

    def test_tampering_action_breaks_hash(self):
        chain = build_synthetic_chain(5)
        target_idx = 1
        orig = chain[target_idx]

        # Change action from UPDATE to DELETE or lowercase update
        for forged_action in ["DELETE", "CREATE", "update", "SYNC"]:
            if forged_action == orig.action:
                continue
            new_hash = ExternalResourceAuditRecord.compute_hash(
                orig.resource_id, orig.timestamp, orig.actor, forged_action, orig.payload, orig.prev_hash
            )
            assert new_hash != orig.current_hash

            tampered_rec = ExternalResourceAuditRecord(
                id=orig.id,
                resource_id=orig.resource_id,
                timestamp=orig.timestamp,
                actor=orig.actor,
                action=forged_action,
                payload=orig.payload,
                prev_hash=orig.prev_hash,
                current_hash=orig.current_hash,
            )
            tampered_chain = list(chain)
            tampered_chain[target_idx] = tampered_rec
            valid, failed_idx, _ = verify_audit_chain(tampered_chain)
            assert valid is False
            assert failed_idx == target_idx

    def test_tampering_actor_breaks_hash(self):
        chain = build_synthetic_chain(5)
        target_idx = 3
        orig = chain[target_idx]

        # Attempt to spoof actor to an innocent user or system
        spoofed_actor = "system_operator_root"
        new_hash = ExternalResourceAuditRecord.compute_hash(
            orig.resource_id, orig.timestamp, spoofed_actor, orig.action, orig.payload, orig.prev_hash
        )
        assert new_hash != orig.current_hash

        tampered_rec = ExternalResourceAuditRecord(
            id=orig.id,
            resource_id=orig.resource_id,
            timestamp=orig.timestamp,
            actor=spoofed_actor,
            action=orig.action,
            payload=orig.payload,
            prev_hash=orig.prev_hash,
            current_hash=orig.current_hash,
        )
        chain[target_idx] = tampered_rec
        valid, failed_idx, _ = verify_audit_chain(chain)
        assert valid is False
        assert failed_idx == target_idx

    def test_tampering_resource_id_breaks_hash(self):
        chain = build_synthetic_chain(5)
        orig = chain[0]
        tampered_id = "unauthorized-resource-target"

        new_hash = ExternalResourceAuditRecord.compute_hash(
            tampered_id, orig.timestamp, orig.actor, orig.action, orig.payload, orig.prev_hash
        )
        assert new_hash != orig.current_hash

    def test_tampering_prev_hash_breaks_linkage(self):
        chain = build_synthetic_chain(5)
        target_idx = 2
        orig = chain[target_idx]

        # Flip a single character in prev_hash
        char_list = list(orig.prev_hash)
        char_list[0] = "f" if char_list[0] != "f" else "0"
        corrupted_prev_hash = "".join(char_list)

        tampered_rec = ExternalResourceAuditRecord(
            id=orig.id,
            resource_id=orig.resource_id,
            timestamp=orig.timestamp,
            actor=orig.actor,
            action=orig.action,
            payload=orig.payload,
            prev_hash=corrupted_prev_hash,
            current_hash=orig.current_hash,
        )
        chain[target_idx] = tampered_rec
        valid, failed_idx, msg = verify_audit_chain(chain)
        assert valid is False
        assert failed_idx == target_idx
        assert "Broken chain link" in msg

    def test_adversary_recomputes_current_hash_but_breaks_next_block(self):
        """
        Sophisticated attack: The adversary modifies block k AND recomputes block k's current_hash
        so that block k appears internally valid.
        Empirical check: Block k+1 MUST fail because its recorded prev_hash points to the old hash!
        """
        chain = build_synthetic_chain(10)
        target_idx = 3

        orig = chain[target_idx]
        tampered_payload = {**orig.payload, "injected_backdoor": True}

        forged_current_hash = ExternalResourceAuditRecord.compute_hash(
            orig.resource_id,
            orig.timestamp,
            orig.actor,
            orig.action,
            tampered_payload,
            orig.prev_hash,
        )
        assert forged_current_hash != orig.current_hash

        forged_rec = ExternalResourceAuditRecord(
            id=orig.id,
            resource_id=orig.resource_id,
            timestamp=orig.timestamp,
            actor=orig.actor,
            action=orig.action,
            payload=tampered_payload,
            prev_hash=orig.prev_hash,
            current_hash=forged_current_hash,
        )
        chain[target_idx] = forged_rec

        # Block target_idx is internally consistent:
        assert ExternalResourceAuditRecord.compute_hash(
            forged_rec.resource_id,
            forged_rec.timestamp,
            forged_rec.actor,
            forged_rec.action,
            forged_rec.payload,
            forged_rec.prev_hash,
        ) == forged_rec.current_hash

        # BUT the chain as a whole fails immediately at target_idx + 1:
        valid, failed_idx, msg = verify_audit_chain(chain)
        assert valid is False
        assert failed_idx == target_idx + 1
        assert f"Broken chain link at index {target_idx + 1}" in msg

    def test_merkle_canonical_serialization_key_order_invariance(self):
        """
        Confirms that dictionary key order does NOT alter the hash.
        Payloads with identical keys/values in different dictionary insertion order
        must produce identical SHA-256 hashes.
        """
        payload_1 = {"alpha": 1, "beta": 2, "gamma": {"x": 10, "y": 20}}
        payload_2 = {"gamma": {"y": 20, "x": 10}, "beta": 2, "alpha": 1}

        h1 = ExternalResourceAuditRecord.compute_hash(
            "res-1", "2026-09-12T12:00:00Z", "admin", "UPDATE", payload_1, "0" * 64
        )
        h2 = ExternalResourceAuditRecord.compute_hash(
            "res-1", "2026-09-12T12:00:00Z", "admin", "UPDATE", payload_2, "0" * 64
        )
        assert h1 == h2, "Hash calculation must be invariant to dict key ordering!"

    def test_merkle_unicode_and_special_character_stability(self):
        payload = {
            "name": "Foundry \u6771\u4eac\u30d7\u30ed\u30b8\u30a7\u30af\u30c8",  # Tokyo Project
            "quote": "Crème brûlée & 'special' \"symbols\" <xml> \n\t\r",
            "emoji": "🚀🤖🛡️",
        }
        h1 = ExternalResourceAuditRecord.compute_hash(
            "res-unicode", "2026-09-12T12:00:00Z", "dave@vulcan.io", "CREATE", payload, "0" * 64
        )
        h2 = ExternalResourceAuditRecord.compute_hash(
            "res-unicode", "2026-09-12T12:00:00Z", "dave@vulcan.io", "CREATE", copy.deepcopy(payload), "0" * 64
        )
        assert h1 == h2
        assert len(h1) == 64

    def test_empty_and_large_payload_boundaries(self):
        # Empty payload
        h_empty = ExternalResourceAuditRecord.compute_hash(
            "res-empty", "2026-09-12T12:00:00Z", "admin", "TEST", {}, "0" * 64
        )
        assert len(h_empty) == 64

        # Large 100KB payload
        large_payload = {f"k_{i}": f"v_{i}" * 50 for i in range(1000)}
        h_large = ExternalResourceAuditRecord.compute_hash(
            "res-large", "2026-09-12T12:00:00Z", "admin", "SYNC", large_payload, "0" * 64
        )
        assert len(h_large) == 64
        assert h_empty != h_large


# =====================================================================
# 2. CONCURRENCY & STRICT IMMUTABILITY SUITE
# =====================================================================

class TestEntityImmutabilityAndDefense:
    """Verifies frozen immutability and memory isolation of supporting entities."""

    def test_external_resource_version_is_strictly_frozen(self):
        v = ExternalResourceVersion(
            id=1,
            resource_id="foundry-dev",
            revision=3,
            snapshot={"endpoint": "https://dev.azure.com"},
            actor="admin.alice",
            reason="Configuration upgrade",
        )

        with pytest.raises(FrozenInstanceError):
            v.revision = 4  # type: ignore

        with pytest.raises(FrozenInstanceError):
            v.resource_id = "hacked-id"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            v.actor = "hacker"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            v.snapshot = {}  # type: ignore

        with pytest.raises(FrozenInstanceError):
            v.reason = "malicious reason"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            delattr(v, "reason")

        assert v.revision == 3
        assert v.actor == "admin.alice"

    def test_external_resource_health_is_strictly_frozen(self):
        h = ExternalResourceHealth(
            id=10,
            resource_id="foundry-dev",
            status=HealthStatus.CONNECTED,
            latency_ms=45.5,
            http_status=200,
            message="Healthy connection",
            diagnostics={"active": True},
        )

        with pytest.raises(FrozenInstanceError):
            h.status = HealthStatus.DEGRADED  # type: ignore

        with pytest.raises(FrozenInstanceError):
            h.latency_ms = 999.9  # type: ignore

        with pytest.raises(FrozenInstanceError):
            h.http_status = 500  # type: ignore

        with pytest.raises(FrozenInstanceError):
            h.message = "Forged message"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            delattr(h, "latency_ms")

        assert h.status == HealthStatus.CONNECTED
        assert h.latency_ms == 45.5

    def test_external_resource_audit_record_is_strictly_frozen(self):
        rec = ExternalResourceAuditRecord(
            id=1,
            resource_id="foundry-dev",
            timestamp="2026-09-12T12:00:00Z",
            actor="admin.dave",
            action="CREATE",
            payload={"provider": "microsoft_foundry"},
            prev_hash="0" * 64,
            current_hash="abcd" * 16,
        )

        with pytest.raises(FrozenInstanceError):
            rec.current_hash = "0" * 64  # type: ignore

        with pytest.raises(FrozenInstanceError):
            rec.actor = "intruder"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            rec.action = "DELETE"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            rec.prev_hash = "1" * 64  # type: ignore

        with pytest.raises(FrozenInstanceError):
            delattr(rec, "current_hash")

        assert rec.current_hash == "abcd" * 16
        assert rec.actor == "admin.dave"

    def test_to_dict_deep_copy_isolation(self):
        """
        Verifies that modifying the dictionary returned by to_dict() does NOT
        mutate internal state of frozen objects.
        """
        # 1. ExternalResourceVersion
        v = ExternalResourceVersion(
            id=1,
            resource_id="res-1",
            revision=1,
            snapshot={"nested": {"param": 100}},
            actor="admin",
        )
        d_v = v.to_dict()
        d_v["snapshot"]["nested"]["param"] = 999
        assert v.snapshot["nested"]["param"] == 100, "Version snapshot was mutated via to_dict() leak!"

        # 2. ExternalResourceHealth
        h = ExternalResourceHealth(
            resource_id="res-1",
            status=HealthStatus.CONNECTED,
            latency_ms=10.0,
            diagnostics={"probes": [1, 2, 3]},
        )
        d_h = h.to_dict()
        d_h["diagnostics"]["probes"].append(4)
        assert len(h.diagnostics["probes"]) == 3, "Health diagnostics was mutated via to_dict() leak!"

        # 3. ExternalResourceAuditRecord
        rec = ExternalResourceAuditRecord(
            resource_id="res-1",
            timestamp="2026-09-12T12:00:00Z",
            actor="admin",
            action="CREATE",
            payload={"deployments": ["gpt-4o"]},
            prev_hash="0" * 64,
            current_hash="f" * 64,
        )
        d_rec = rec.to_dict()
        d_rec["payload"]["deployments"].append("malicious-deployment")
        assert len(rec.payload["deployments"]) == 1, "Audit payload was mutated via to_dict() leak!"

    def test_concurrent_reads_on_frozen_entities(self):
        """
        Validates high-concurrency read safety: 50 concurrent worker threads
        repeatedly reading attributes and converting frozen objects to dicts.
        """
        rec = ExternalResourceAuditRecord(
            resource_id="res-concurrency",
            timestamp="2026-09-12T12:00:00Z",
            actor="admin.dave",
            action="CREATE",
            payload={"cluster": "prod-east", "nodes": 12},
            prev_hash="0" * 64,
            current_hash="e" * 64,
        )
        errors: List[Exception] = []

        def worker():
            try:
                for _ in range(100):
                    d = rec.to_dict()
                    assert d["resource_id"] == "res-concurrency"
                    assert d["payload"]["nodes"] == 12
                    assert rec.current_hash == "e" * 64
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors on frozen record: {errors}"


# =====================================================================
# 3. MONOTONIC REVISION INCREMENTS SUITE
# =====================================================================

class TestMonotonicRevisionIncrements:
    """Verifies strict monotonic revision progression and transaction-like atomicity."""

    def test_strict_monotonic_revision_progression_100_updates(self):
        res = ExternalResource(
            resource_id="res-mono",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Foundry AI Instance",
            endpoint="https://foundry-prod.services.ai.azure.com/api/projects/p1",
            revision=1,
        )
        assert res.revision == 1

        for step in range(1, 101):
            expected_rev = step + 1
            actor_name = f"user.{step}"
            res.update_configuration(
                config={"step": step, "active": True},
                actor=actor_name,
                display_name=f"Foundry AI Step {step}",
            )
            assert res.revision == expected_rev, f"Revision did not increment monotonically at step {step}"
            assert res.config["step"] == step
            assert res.updated_by == actor_name
            assert res.display_name == f"Foundry AI Step {step}"

    def test_update_configuration_atomicity_on_secret_lint_failure(self):
        """
        If update_configuration receives raw credentials in config,
        it must raise SecretLintError and NEVER bump revision or change config.
        """
        res = ExternalResource(
            resource_id="res-atomic-1",
            provider="github",
            category=ResourceCategory.SOURCE_CONTROL,
            display_name="GitHub Enterprise",
            endpoint="https://github.corp",
            revision=5,
            config={"safe_param": "original_value"},
        )
        assert res.revision == 5

        # Attempt forbidden config update
        bad_config = {
            "safe_param": "tampered_value",
            "password": "RawPlaintextPassword123!",
        }

        with pytest.raises(SecretLintError) as exc_info:
            res.update_configuration(
                config=bad_config,
                actor="attacker",
            )
        assert "Security Invariant Triggered" in str(exc_info.value)

        # Invariant checks:
        assert res.revision == 5, "Revision must NOT increment on lint failure!"
        assert res.config == {"safe_param": "original_value"}, "Config must NOT be mutated on failure!"
        assert res.updated_by == "system", "updated_by must remain unchanged on failure!"

    def test_update_configuration_atomicity_on_invalid_secret_ref(self):
        """
        If update_configuration receives an invalid URI scheme in secret_refs,
        it must raise SecretLintError and leave revision untouched.
        """
        res = ExternalResource(
            resource_id="res-atomic-2",
            provider="cyberark",
            category=ResourceCategory.SECRETS_PAM,
            display_name="CyberArk Vault",
            endpoint="https://cyberark.corp",
            revision=10,
            secret_refs={"root": "cyberark://vault/root"},
        )
        assert res.revision == 10

        bad_secret_refs = {
            "root": "http://plain-http-leak/secret",
        }

        with pytest.raises(SecretLintError) as exc_info:
            res.update_configuration(
                config={"new_param": 1},
                secret_refs=bad_secret_refs,
                actor="bad_actor",
            )
        assert "invalid scheme" in str(exc_info.value).lower()

        assert res.revision == 10, "Revision must NOT increment on invalid secret_refs!"
        assert res.secret_refs == {"root": "cyberark://vault/root"}
        assert res.config == {}

    def test_update_configuration_atomicity_on_type_errors(self):
        res = ExternalResource(
            resource_id="res-atomic-3",
            provider="postgres",
            category=ResourceCategory.STORAGE_DATA,
            display_name="Postgres DB",
            endpoint="postgresql://db:5432/main",
            revision=2,
        )

        with pytest.raises(ParameterValidationError):
            res.update_configuration(config="not-a-dict")  # type: ignore
        assert res.revision == 2

        with pytest.raises(ParameterValidationError):
            res.update_configuration(config={}, secret_refs="not-a-dict")  # type: ignore
        assert res.revision == 2

    def test_update_configuration_partial_fields_preserve_existing(self):
        """
        Providing secret_refs=None or omitting endpoint/display_name/enabled
        must preserve existing attributes while bumping revision exactly once.
        """
        res = ExternalResource(
            resource_id="res-partial",
            provider="redis",
            category=ResourceCategory.STORAGE_DATA,
            display_name="Redis Cache",
            endpoint="redis://127.0.0.1:6379",
            enabled=True,
            secret_refs={"auth_token": "vault://secret/redis#token"},
            revision=1,
        )

        res.update_configuration(
            config={"max_memory_mb": 4096},
            actor="admin.bob",
            # secret_refs omitted
            # endpoint omitted
            # display_name omitted
            # enabled omitted
        )

        assert res.revision == 2
        assert res.config == {"max_memory_mb": 4096}
        assert res.secret_refs == {"auth_token": "vault://secret/redis#token"}
        assert res.endpoint == "redis://127.0.0.1:6379"
        assert res.display_name == "Redis Cache"
        assert res.enabled is True
        assert res.updated_by == "admin.bob"

    def test_instantiation_revision_bounds(self):
        """Validates that revision cannot be initialized below 1."""
        with pytest.raises(ParameterValidationError) as exc:
            ExternalResource(
                resource_id="res-bad-rev",
                provider="aap",
                category=ResourceCategory.EXECUTION,
                display_name="Ansible Automation Platform",
                endpoint="https://aap.corp",
                revision=0,
            )
        assert "revision must be >= 1" in str(exc.value)

        with pytest.raises(ParameterValidationError):
            ExternalResource(
                resource_id="res-bad-rev-2",
                provider="aap",
                category=ResourceCategory.EXECUTION,
                display_name="Ansible Automation Platform",
                endpoint="https://aap.corp",
                revision=-10,
            )

    def test_concurrent_updates_under_lock_guarantees_monotonicity(self):
        """
        Simulates the repository concurrency model (using threading.RLock, as specified
        for PostgresExternalResourceRepository in-memory cache) to verify that
        50 concurrent updates sequentially increment revision with zero lost updates.
        """
        res = ExternalResource(
            resource_id="res-concurrent-updates",
            provider="microsoft_foundry",
            category=ResourceCategory.AI_MODELS,
            display_name="Foundry Target",
            endpoint="https://foundry-prod.services.ai.azure.com",
            revision=1,
        )
        lock = threading.RLock()
        errors: List[Exception] = []

        def updater(thread_id: int):
            try:
                for i in range(10):
                    with lock:
                        res.update_configuration(
                            config={"last_thread": thread_id, "iter": i},
                            actor=f"worker-{thread_id}",
                        )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(t_id,)) for t_id in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Started at 1, 10 threads * 10 iterations = 100 updates -> revision should be exactly 101
        assert res.revision == 101, f"Expected revision 101, got {res.revision} (lost updates detected!)"
