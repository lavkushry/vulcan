# HACKATHON.md — Vulcan Submission Evidence

> **Vulcan** is a governed AI control plane that converts infrastructure intent
> into approved, immutable, and verifiably executed automation — without
> fabricating success.

---

## Problem

Infrastructure teams today face a trade-off: manual processes that are slow and
error-prone, or fully automated pipelines that lack governance and auditability.
In regulated industries, both extremes are unacceptable.

## Target Users

- Platform engineers managing fleet-scale infrastructure
- SREs who need governed, auditable automation
- Security teams requiring separation of duties and cryptographic audit trails
- Compliance officers who need provable execution evidence

## Solution

Vulcan introduces an **AI-governed control plane** — a multi-agent system where:

1. An **Intent Agent** interprets natural-language requests into structured automation parameters
2. A **Discovery Agent** finds matching automation artifacts from a curated catalog
3. A **Planner Agent** decides whether to compose, generate, or select existing artifacts
4. A **Resource Agent** resolves all external dependencies (credentials, ITSM tickets, storage)
5. A **Validation Agent** performs syntax, lint, and security checks
6. A **Policy Engine** enforces risk-based approval requirements
7. A **Constrained Executor** runs automation under capability-token-scoped permissions
8. A **Verification Agent** independently confirms desired state was achieved
9. A **Cryptographic Audit Ledger** records a SHA-256 hash-chained event trail

## Architecture

```
User Request (natural language)
        │
        ▼
┌─────────────────────────────────────────┐
│  AgentOS Kernel (orchestrator)          │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐  │
│  │ Intent  │→│ Discovery│→│ Planner │  │
│  └─────────┘ └──────────┘ └─────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐  │
│  │Composer │→│ Resource │→│Validator│  │
│  └─────────┘ └──────────┘ └─────────┘  │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐  │
│  │Security │→│  Critic  │→│ Policy  │  │
│  └─────────┘ └──────────┘ └─────────┘  │
│  ┌─────────────┐ ┌────────────────────┐ │
│  │  Executor   │→│   Verifier         │ │
│  │ (cap-token) │ │ (desired-state)    │ │
│  └─────────────┘ └────────────────────┘ │
│  ┌────────────────────────────────────┐  │
│  │  Audit Ledger (SHA-256 chain)     │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│  Next.js 15 Dashboard                  │
│  Chat · Matrix · Policies · Audit      │
└─────────────────────────────────────────┘
```

## Responsible AI & Safety Controls

| Control | Implementation |
|---|---|
| No fabricated success | Execution results verified independently against desired state. Missing metrics display "Not measured". |
| Maker-checker approval | Requester cannot self-approve. `WORKFLOW_APPROVE` permission enforced separately from `WORKFLOW_ADVANCE`. |
| Environment isolation | Cross-environment resource fallback is forbidden. DEV credentials cannot satisfy PROD workflows. |
| Capability-token execution | Executor receives a signed token scoping allowed file paths and SHA-256 artifact digest. Violations → `SECURITY_REJECTED`. |
| Fail-closed authentication | Unconfigured authentication rejects all requests. Development tokens require explicit opt-in. |
| Unknown provider rejection | Unrecognized connection providers return an error, not a fabricated health check. |
| Ansible missing detection | When `ansible-playbook` is absent, exit code 127 is returned — no fake recap generated. |

## What Is Genuinely Live

- Multi-agent kernel orchestrating 10+ specialist agents through a 20-state workflow FSM
- FastAPI backend with PostgreSQL persistence, optimistic locking, and event sourcing
- Next.js 15 frontend with 18 compiled pages
- Cryptographic SHA-256 hash-chained audit ledger
- Capability-token-scoped execution with artifact SHA verification
- Maker-checker separation of duties with permission enforcement
- Resource dependency resolution with environment-scoped isolation
- 50-scenario evaluation framework with automated grading

## What Is Simulated

- Ansible execution uses a simulation adapter when `ansible-playbook` is not installed
- LLM-powered intent parsing uses rule-based pattern matching (no live LLM API calls)
- External integrations (ServiceNow, CyberArk, Datadog) use mock adapters
- Registry downloads fall back to local cache when registry is unavailable

## Reproduction Steps

```bash
# Clone and run tests
git clone https://github.com/lavkushry/vulcan.git
cd vulcan-control-plane

# Backend tests (requires Python 3.14+)
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -q

# Frontend build (requires Node.js 20+)
cd ../frontend
npm install
npm run build

# Full demo (requires Docker)
cd ..
make demo
```

## Evaluation Methodology

- **Unit & integration tests**: 615 passed, 9 skipped, 0 failed
- **50-scenario eval framework**: Tests canonical workflows across intent parsing, resource resolution, approval enforcement, execution, and verification
- **Release gate tests**: 8 dedicated tests verifying 7 critical safety invariants (ansible missing, registry unavailable, environment isolation, approval authorization, failing playbook detection, omitted evidence, worker restart recovery)
- **Frontend build**: 18 pages compiled with 0 TypeScript errors

## Machine-Generated Evidence

| Metric | Value |
|---|---|
| Commit SHA | `6959634` (head of main at submission) |
| Backend test suite | 615 passed, 9 skipped, 0 failures |
| Eval scenario gate | All scenarios pass |
| Frontend build | 18 pages, exit code 0 |
| False-success rate | 0% (ansible missing returns exit 127, not fake recap) |
| Unauthorized approval attempts | Blocked with HTTP 403 |
| Tracked secrets | 0 (SSH keys removed, ephemeral generation at container startup) |

## Known Limitations

1. LLM intent parsing uses rule-based matching — no live model API calls
2. External integrations (ServiceNow, CyberArk, Datadog) use mock adapters
3. Ansible execution requires the binary installed on the host/container
4. The 50-scenario eval framework tests workflow logic, not live infrastructure
5. Production deployment requires real PostgreSQL, Redis, and MinIO instances

## Demo Script

### Flagship Flow: Deploy PostgreSQL 16

1. **Request**: User types "Deploy PostgreSQL 16 on the approved target" in the chat interface
2. **Intent Resolution**: Vulcan extracts `db_version=16`, `automation_domain=database`, selects a curated catalog artifact
3. **Resource Check**: All required dependencies (CyberArk credentials, ServiceNow ticket, S3 backup) are verified
4. **Policy Gate**: Risk assessment determines PROD deployment requires maker-checker approval
5. **Approval**: A different user with `WORKFLOW_APPROVE` permission signs off
6. **Execution**: Constrained executor runs the artifact under capability-token scope
7. **Verification**: Independent probes confirm PostgreSQL is running, accepting connections, and matching desired state
8. **Audit**: Hash-chained event log proves the complete execution chain from intent to verification

---

*Generated for hackathon submission. All claims are backed by automated tests in the repository.*
