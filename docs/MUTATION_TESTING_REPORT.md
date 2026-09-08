# Project Vulcan: Domain Governance Mutation Testing Report (Milestone C.2)

**Generated**: 2026-09-08 06:32:27 UTC  
**Target Domain Subsystems**: `backend/app/domain/entities.py` & `backend/app/domain/roles_and_policies.py`  
**Total Governance Mutants**: 46  
**Killed Mutants**: 46  
**Survived Mutants**: 0  
**Targeted Governance Mutant Kill Score**: **100.0%** (46/46 killed)  

> [!IMPORTANT]
> **Framing & Scope**: *Score is over 46 hand-authored governance mutants, not exhaustive AST-level mutation; coverage is as broad as the mutant set.*

---

## 1. Executive Summary & Regulatory Significance

In banking automation platforms, standard line and branch coverage can easily create a false sense of security. A suite can achieve 90%+ line coverage while completely missing governance bypasses (e.g. self-approval conditional branches evaluated falsely, approval timeout calculations bypassed, or candidate execution checks removed).

Milestone C.2 introduces an automated, hand-rolled domain mutation engine targeting **46 precision governance mutants** across seven core banking invariant categories:

| Category | Mutants | Invariant Guarded | Regulatory / Architecture Mandate |
|---|---|---|---|
| **MAKER_CHECKER** | 6 | Absolute Separation of Duties (Four-Eyes Principle) | SOX Section 404, PNC Core Invariant |
| **APPROVAL_TIMEOUT** | 5 | 15-Minute Fail-Closed Expiration Window | Operational Risk & Circuit Breakers |
| **STATE_MACHINE** | 11 | Complete Transition Closure & Terminal Immutability | Deterministic FSM Integrity |
| **STEEL_CAGE** | 4 | INV-1: CANDIDATE vs CURATED (SHA-40 Binding) | Software Supply Chain Security |
| **PARAMETER_VALIDATION** | 11 | Schema, Bounds, Regex & TruffleHog Secret Linting | Zero Credential Leakage & Memory Safety |
| **RBAC_AND_POLICY** | 6 | Policy-as-Code & Least Privilege Role Enforcements | Enterprise Authorization & Freeze Windows |
| **MERKLE_CHAIN** | 3 | Cryptographic Prev-Hash Ledger Tamper Detection | Immutable Forensic Audit Trail |

---

## 2. Complete Mutant Execution Matrix

| ID | Category | Status | Duration | Targeted Test Suite | Mutation Description |
|---|---|---|---|---|---|
| `MUT-MC-01` | **MAKER_CHECKER** | ✅ KILLED | 0.65s | `backend/tests/test_state_machine_mutations.py` | Bypass self-approval block in apply_approval_decision (always allow requester to approve) |
| `MUT-MC-02` | **MAKER_CHECKER** | ✅ KILLED | 1.08s | `backend/tests/test_state_machine_mutations.py` | Invert Maker-Checker inequality in apply_approval_decision (!= instead of ==) |
| `MUT-MC-03` | **MAKER_CHECKER** | ✅ KILLED | 1.21s | `backend/tests/test_state_machine_mutations.py` | Bypass self-approval check in enforce_maker_checker |
| `MUT-MC-04` | **MAKER_CHECKER** | ✅ KILLED | 1.24s | `backend/tests/test_state_machine_mutations.py` | Invert Maker-Checker in enforce_maker_checker (!= instead of ==) |
| `MUT-MC-05` | **MAKER_CHECKER** | ✅ KILLED | 1.87s | `backend/tests/test_policy_engine.py` | Bypass POL-001 Maker-Checker invariant in PolicyEngine.evaluate |
| `MUT-MC-06` | **MAKER_CHECKER** | ✅ KILLED | 1.61s | `backend/tests/test_policy_engine.py` | Bypass POL-001 Approving Lead requirement for PROD High-Risk jobs without approver |
| `MUT-TO-01` | **APPROVAL_TIMEOUT** | ✅ KILLED | 1.06s | `backend/tests/test_state_machine_mutations.py` | Disable 15-minute approval timeout check in apply_approval_decision |
| `MUT-TO-02` | **APPROVAL_TIMEOUT** | ✅ KILLED | 1.38s | `backend/tests/test_state_machine_mutations.py` | Invert timeout check in apply_approval_decision (elapsed < timeout_seconds) |
| `MUT-TO-03` | **APPROVAL_TIMEOUT** | ✅ KILLED | 1.41s | `backend/tests/test_state_machine_mutations.py` | Omit transition to TIMEOUT_DENIED on expired approval in apply_approval_decision |
| `MUT-TO-04` | **APPROVAL_TIMEOUT** | ✅ KILLED | 1.33s | `backend/tests/test_state_machine_mutations.py` | Disable 15-minute timeout check in enforce_maker_checker |
| `MUT-TO-05` | **APPROVAL_TIMEOUT** | ✅ KILLED | 1.47s | `backend/tests/test_state_machine_mutations.py` | Omit raising ApprovalTimeoutError in enforce_maker_checker |
| `MUT-FSM-01` | **STATE_MACHINE** | ✅ KILLED | 1.28s | `backend/tests/test_state_machine_mutations.py` | Allow illegal SUBMITTED -> RUNNING skip transition |
| `MUT-FSM-02` | **STATE_MACHINE** | ✅ KILLED | 1.59s | `backend/tests/test_state_machine_mutations.py` | Allow illegal PARSED -> RUNNING skip transition |
| `MUT-FSM-03` | **STATE_MACHINE** | ✅ KILLED | 1.35s | `backend/tests/test_state_machine_mutations.py` | Allow illegal PENDING_APPROVAL -> RUNNING skip transition |
| `MUT-FSM-04` | **STATE_MACHINE** | ✅ KILLED | 1.31s | `backend/tests/test_state_machine_mutations.py` | Allow terminal SUCCESS state resurrection to RUNNING |
| `MUT-FSM-05` | **STATE_MACHINE** | ✅ KILLED | 1.26s | `backend/tests/test_state_machine_mutations.py` | Allow terminal FAILED state resurrection to RUNNING |
| `MUT-FSM-06` | **STATE_MACHINE** | ✅ KILLED | 1.3s | `backend/tests/test_state_machine_mutations.py` | Allow terminal TIMEOUT_DENIED resurrection to QUEUED |
| `MUT-FSM-07` | **STATE_MACHINE** | ✅ KILLED | 1.23s | `backend/tests/test_state_machine_mutations.py` | Allow terminal REJECTED resurrection to QUEUED |
| `MUT-FSM-08` | **STATE_MACHINE** | ✅ KILLED | 1.5s | `backend/tests/test_state_machine_mutations.py` | Allow terminal REVERTED resurrection to RUNNING |
| `MUT-FSM-09` | **STATE_MACHINE** | ✅ KILLED | 1.23s | `backend/tests/test_state_machine_mutations.py` | Disable state transition guard in transition_to (open transition matrix) |
| `MUT-FSM-10` | **STATE_MACHINE** | ✅ KILLED | 1.37s | `backend/tests/test_state_machine_mutations.py` | Omit state precondition check in apply_approval_decision |
| `MUT-FSM-11` | **STATE_MACHINE** | ✅ KILLED | 1.12s | `backend/tests/test_state_machine_mutations.py` | Omit state precondition check in enforce_maker_checker |
| `MUT-SC-01` | **STEEL_CAGE** | ✅ KILLED | 1.33s | `backend/tests/test_state_machine_mutations.py` | Disable 40-character SHA-1 verification for CURATED CatalogItem |
| `MUT-SC-02` | **STEEL_CAGE** | ✅ KILLED | 1.91s | `backend/tests/test_state_machine_mutations.py` | Allow CANDIDATE CatalogItem to have non-null Git commit SHA |
| `MUT-SC-03` | **STEEL_CAGE** | ✅ KILLED | 1.31s | `backend/tests/test_state_machine_mutations.py` | Allow CANDIDATE CatalogItem to execute (can_execute returns True always) |
| `MUT-SC-04` | **STEEL_CAGE** | ✅ KILLED | 1.17s | `backend/tests/test_state_machine_mutations.py` | Invert can_execute logic (CURATED cannot execute, CANDIDATE can) |
| `MUT-PV-01` | **PARAMETER_VALIDATION** | ✅ KILLED | 0.81s | `backend/tests/test_state_machine_mutations.py` | Disable required parameter presence verification |
| `MUT-PV-02` | **PARAMETER_VALIDATION** | ✅ KILLED | 0.85s | `backend/tests/test_state_machine_mutations.py` | Disable string type validation on parameters |
| `MUT-PV-03` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.12s | `backend/tests/test_state_machine_mutations.py` | Disable numeric type validation (allow string or bool for numbers) |
| `MUT-PV-04` | **PARAMETER_VALIDATION** | ✅ KILLED | 0.85s | `backend/tests/test_state_machine_mutations.py` | Disable regex pattern matching on string parameters |
| `MUT-PV-05` | **PARAMETER_VALIDATION** | ✅ KILLED | 0.84s | `backend/tests/test_state_machine_mutations.py` | Disable minimum bound validation on numeric parameters |
| `MUT-PV-06` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.0s | `backend/tests/test_state_machine_mutations.py` | Disable maximum bound validation on numeric parameters |
| `MUT-PV-07` | **PARAMETER_VALIDATION** | ✅ KILLED | 0.99s | `backend/tests/test_state_machine_mutations.py` | Disable ServiceNow Change Request (CHG ticket) requirement on CatalogItem |
| `MUT-PV-08` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.09s | `backend/tests/test_state_machine_mutations.py` | Disable TruffleHog pre-flight secret linting invocation |
| `MUT-PV-09` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.17s | `backend/tests/test_state_machine_mutations.py` | Remove RSA/EC Private Key detection regex from _lint_secret |
| `MUT-PV-10` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.32s | `backend/tests/test_state_machine_mutations.py` | Remove AWS AKIA access key detection regex from _lint_secret |
| `MUT-PV-11` | **PARAMETER_VALIDATION** | ✅ KILLED | 1.34s | `backend/tests/test_state_machine_mutations.py` | Remove high-entropy password/token assignment regex from _lint_secret |
| `MUT-RBAC-01` | **RBAC_AND_POLICY** | ✅ KILLED | 2.63s | `backend/tests/test_policy_engine.py` | Illegally grant Permission.JOB_APPROVE to UserRole.OPERATOR |
| `MUT-RBAC-02` | **RBAC_AND_POLICY** | ✅ KILLED | 2.23s | `backend/tests/test_policy_engine.py` | Strip Permission.JOB_APPROVE from UserRole.APPROVING_LEAD |
| `MUT-RBAC-03` | **RBAC_AND_POLICY** | ✅ KILLED | 2.47s | `backend/tests/test_policy_engine.py` | Disable UserRole JOB_REQUEST permission check in PolicyEngine.evaluate |
| `MUT-RBAC-04` | **RBAC_AND_POLICY** | ✅ KILLED | 1.62s | `backend/tests/test_policy_engine.py` | Bypass POL-002 ServiceNow CHG ticket check for PROD HIGH/MEDIUM jobs |
| `MUT-RBAC-05` | **RBAC_AND_POLICY** | ✅ KILLED | 1.42s | `backend/tests/test_policy_engine.py` | Bypass POL-003 Secret Linting check in PolicyEngine.evaluate |
| `MUT-RBAC-06` | **RBAC_AND_POLICY** | ✅ KILLED | 1.08s | `backend/tests/test_policy_engine.py` | Bypass POL-005 Operational Freeze Window enforcement |
| `MUT-MK-01` | **MERKLE_CHAIN** | ✅ KILLED | 0.62s | `backend/tests/test_state_machine_mutations.py` | Omit prev_hash from AuditRecord.compute_hash (breaks Merkle chaining) |
| `MUT-MK-02` | **MERKLE_CHAIN** | ✅ KILLED | 0.71s | `backend/tests/test_state_machine_mutations.py` | Substitute static constant hash instead of SHA-256 computation |
| `MUT-MK-03` | **MERKLE_CHAIN** | ✅ KILLED | 1.11s | `backend/tests/test_state_machine_mutations.py` | Omit action from AuditRecord cryptographic payload |

---

## 3. Invariant Verification & Kill Mechanisms

1. **Universal Maker-Checker (SOX 404)**: Mutations attempting to equate `approver_id == requester_id` or short-circuit the inequality check were caught immediately by `test_mutation_self_approval_bypass_rejected` and `test_maker_checker_invariants`.
2. **15-Minute Expiry Window**: Inverting or removing the `elapsed > timeout_seconds` check fails closed with `test_mutation_approval_timeout_bypass_rejected` and `test_mutation_enforce_maker_checker_timeout_fails_closed`.
3. **FSM Transition Closure**: Adding transitions from `SUBMITTED -> RUNNING` or `PARSED -> RUNNING`, or reviving terminal states (`SUCCESS`, `FAILED`, `TIMEOUT_DENIED`, `REJECTED`), is caught by `test_mutation_parsed_to_running_illegal` and `test_mutation_all_illegal_state_transitions_rejected`.
4. **Steel Cage (INV-1)**: Unlinking commit SHA from CURATED or allowing CANDIDATE to execute is rejected by `test_mutation_steel_cage_curated_sha_and_candidate_null_sha` and `test_mutation_candidate_execution_blocked_under_inv1`.
5. **TruffleHog Secret Linting**: Removing private key or token regex patterns triggers failures in `test_mutation_parameter_secret_linting_private_key_and_assignment`.
6. **Policy-as-Code RBAC**: Illegally assigning `job:approve` to operators, stripping leads, or permitting auditors to request jobs is caught by `test_pol_role_permission_auditor_job_request_denied` and `test_role_permissions_hierarchy`.
7. **Cryptographic Merkle Ledger**: Removing `prev_hash` or `action` from the SHA-256 calculation fails `test_mutation_audit_record_merkle_hash_payload_sensitivity`.

---

## 4. Test Suite Composition & Skipped Test Accounting

Total Test Suite Count: **183 tests** (176 passing, 7 conditionally skipped on local host without active PostgreSQL daemon; 183/183 passing in CI with PostgreSQL container).

| Skipped Test Location | Function Name | Reason for Conditional Skip | CI / Production Status |
|---|---|---|---|
| `backend/tests/test_postgres_catalog.py:81` | `test_postgres_catalog_crud_and_counts` | Local PostgreSQL pgvector not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_catalog.py:156` | `test_hybrid_search_scoring` | Local PostgreSQL pgvector not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_catalog.py:187` | `test_catalog_repository_port_contract` | Local PostgreSQL pgvector not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_catalog.py:205` | `test_pgvector_hnsw_cosine_index_creation` | Local PostgreSQL pgvector not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_catalog.py:238` | `test_transaction_rollback_preserves_curated_state` | Local PostgreSQL pgvector not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_durability.py:383` | `test_postgres_job_repository_crud` | Local PostgreSQL not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |
| `backend/tests/test_postgres_durability.py:425` | `test_postgres_audit_adapter_merkle_chain_integrity` | Local PostgreSQL not accessible on port 5432 | ✅ Executes & passes in CI (pgvector container) |

---

## 5. Verification Gate Sign-Off

- **Targeted Governance Kill Score**: **100.0%** (46/46 killed)
- **Restore Safety**: Verified via `git diff --exit-code backend/app/domain/` (0 residual mutations)
- **Status**: PASS
- **Platform Lead**: Lavkush Kumar (`lavkush@deepmind.com`)
- **Architect**: Robert C. Martin ("Uncle Bob")
