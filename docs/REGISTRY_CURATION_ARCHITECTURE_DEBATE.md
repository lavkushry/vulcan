# PROJECT VULCAN: ENTERPRISE AUTOMATION CONTROL PLANE
## ARCHITECTURAL WAR ROOM: PUBLIC REGISTRY INGESTION, CURATION GATE & SUPPLY CHAIN INTEGRITY
### Rigorous Multi-Perspective Architecture Debate & Consolidated Curation Opportunity Register (REG-XX)

**Date:** September 6, 2026  
**Document Version:** 5.0.0-PROD (Definitive War-Room Record)  
**Classification:** Tier-0 Banking-Grade Automation Governance & Supply-Chain Integrity Blueprint  
**Location:** Mission-Critical War Room 4B, Enterprise Engineering Tower  
**Target Subsystem:** Project Vulcan Registry Crawler Agent, Candidate Store, Curation Gate, Schema Transformer & Stack Composition Engine (`backend/app/adapters/registry_crawler.py`, `backend/app/adapters/terraform_ingestion.py`, `backend/app/adapters/stack_composer.py`, `backend/app/domain/entities.py`, `backend/app/use_cases/runner.py`, `frontend/app/curation/page.tsx`)

---

### EXECUTIVE MANDATE & THE CONSTITUTIONAL PROBLEM

Project Vulcan operates as a banking-grade automation control plane governing Tier-1 financial infrastructure (F5 BIG-IP load balancers, PostgreSQL clusters, Kubernetes worker nodes, and AWS cloud landing zones).

In previous sessions, Vulcan demonstrated:
1. Retrieval across an allowlisted catalog of 110–10,000 items.
2. An intent compiler converting natural language into typed execution parameters.
3. A deterministic execution engine enforcing Maker-Checker dual control, maintenance windows, Redis Redlocks, post-flight health probes, and an immutable SHA-256 Merkle audit ledger.

However, an ambitious proposal was raised:
> *"Why can't Vulcan connect directly to the public Ansible Galaxy and Terraform Registry APIs, dynamically discover any role or module on the internet, let the AI generate playbooks on the fly, and execute them immediately against infrastructure?"*

#### The Forensic Attack & Constitutional Violations Exposed

This proposal, while tempting as a demo shortcut, **violates two foundational laws of the Vulcan Constitution**:

```
THE DEADLY ANTI-PATTERN (WHAT VULCAN STRICTLY PROHIBITS):
Operator Prompt ──▶ Public Registry (Galaxy/TF) ──▶ LLM Writes Code ──▶ RUN AGAINST PRODUCTION
                   [Unvetted Internet Code]        [Dynamic Code Gen]    [CATASTROPHIC RISK]
```

* **Violation 1: INV-1 Steel-Cage Breach ("Collect from registry and run")**:
  Executing unvetted internet code directly against banking infrastructure destroys the fundamental invariant `INV-1` (*allowlist-only, zero execution outside registered, PR-reviewed Git content*). Public registries (Ansible Galaxy, Terraform Registry) contain unmaintained repositories, typosquatting lookalikes, unpinned remote dependencies, malicious `local-exec` provisioners, and zero banking security reviews. The moment the runtime environment can fetch and execute arbitrary internet artifacts, Vulcan ceases to be a governed control plane and becomes an uncontrolled internet script runner with a governance badge.

* **Violation 2: AI Intent Boundary Breach ("LLM authors playbooks")**:
  Dynamic code generation by an LLM at runtime is explicitly banned in Vulcan. An LLM must **compile operator intent into typed parameters for pre-existing, reviewed catalog items**. It must **never** author executable HCL or YAML on the fly, because LLM-generated code cannot be formally verified, cannot be proven free of syntax regressions or destructive defaults, and bypasses the enterprise Change Advisory Board (CAB).

#### The Definitive Architectural Solution: Moving Registries Behind the Catalog Wall

The solution is not to discard public registries, but to **move them to the curation side of the catalog wall**:

```
BEFORE RUNTIME (The Agent's Job: Discovery, Curation, Security Scanning & PR Drafting)
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  REGISTRY CRAWLER AGENT                                                                 │
│  - Scheduled polling of Galaxy + Terraform Registry APIs                                │
│  - Places items into isolated CANDIDATE store (quarantined from execution)              │
│  - Provenance tracking: Upstream URL, version, downloads, author, license classification │
│  - License Gate: Flags BUSL-1.1, SSPL, and non-permissive licenses                      │
│  - Preserves variable defaults as ADVISORY UI HINTS (Zero silent pre-fills)             │
│                                                                                         │
│  CURATION GATE SERVICE & OPERATOR CONSOLE (/curation)                                   │
│  - Automated Vendoring PR Drafting: SHA-256 tarball digest + tfsec/Checkov checklist     │
│  - HUMAN APPROVAL GATE: Demands corporate Git repo URL + reviewed 40-character SHA     │
│  - Promotes candidate to CURATED status (The ONLY doorway into the active catalog)      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                              Promoted to CURATED only
                                           ▼
AT RUNTIME (Zero Unvetted Code Can Execute — INV-1 Enforced)
Operator: "deploy gcp load balancer"
  ──▶ Hybrid Vector/BM25 Search over CURATED catalog only (Candidates invisible)
  ──▶ IntentResolver compiles parameters into NEEDS_INPUT (Advisory hints visible in UI)
  ──▶ Operator confirms parameters ──▶ Two-Stage Plan Diff Card
  ──▶ Maker-Checker Sign-off (requester != approver) ──▶ Redlock Acquisition
  ──▶ BaseJobRunner Step 0 asserts can_execute() ──▶ Execute in Sandboxed Container
  ──▶ Semantic Health Probes ──▶ Tamper-Evident Merkle Audit Commit
```

---

### WAR ROOM PARTICIPANTS

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                WAR ROOM 4B PARTICIPANT MATRIX                                    │
├───────────────────────┬──────────────────────────────────┬───────────────────────────────────────┤
│ ARCHITECT             │ PRIMARY LENS                     │ ATTACK SURFACE IN REGISTRY CURATION   │
├───────────────────────┼──────────────────────────────────┼───────────────────────────────────────┤
│ Robert C. Martin      │ Clean Architecture, Domain       │ Internet code leaking into domain;    │
│ ("Uncle Bob")         │ Invariants, & Boundary Purity    │ candidate isolation; double-lock gate;│
│                       │                                  │ maker-checker curation separation     │
├───────────────────────┼──────────────────────────────────┼───────────────────────────────────────┤
│ Alex Xu               │ Distributed Systems, Capacity    │ Rate limits on public APIs; candidate │
│                       │ & Concurrency                    │ store storage; indexing isolation;    │
│                       │                                  │ deduplication & caching at scale      │
├───────────────────────┼──────────────────────────────────┼───────────────────────────────────────┤
│ Andrej Karpathy       │ AI Boundaries, Schema Typing,    │ Dynamic code gen trap; Rule 2 default │
│                       │ & Non-Guessing Evals             │ non-guessing; intent resolution across│
│                       │                                  │ composite landing zone stacks         │
├───────────────────────┼──────────────────────────────────┼───────────────────────────────────────┤
│ Jordan Walke          │ Declarative UI, State Honesty,   │ Curation deck ergonomics; license     │
│                       │ & Human-in-the-Loop Surfaces     │ warnings; 40-char SHA validation;     │
│                       │                                  │ PR diff cards; keyboard triage        │
├───────────────────────┼──────────────────────────────────┼───────────────────────────────────────┤
│ Platform Lead (Chair) │ Runtime Security, Supply Chain   │ Malicious local-exec; BUSL licensing; │
│                       │ & Release Engineering            │ tfsec/Checkov scans; corporate Git    │
│                       │                                  │ vendoring; immutable artifact pinning │
└───────────────────────┴──────────────────────────────────┴───────────────────────────────────────┘
```

---

### DEBATE SESSION 1: THE IRON BOUNDARY & CANDIDATE ISOLATION

**Uncle Bob:**
Let’s dispense with the pleasantries. Whoever proposed that our execution engine could dynamically pull an arbitrary Ansible role from GitHub or a Terraform module from HashiCorp's registry and run it directly against a banking cluster should be barred from writing production software. In Clean Architecture, dependencies point inward toward high-level policies. The public internet is the most volatile, untrusted, hostile external mechanism that exists. If an entity in your execution runner has a dependency on `registry.terraform.io`, you have coupled your core banking ledger to the whim of an anonymous internet maintainer.

**Platform Lead:**
Bob is 100% right on the threat model. In Terraform modules, an unvetted author can sneak in a `local-exec` provisioner that curls an external webhook exfiltrating AWS IAM STS credentials. In Ansible Galaxy, community roles frequently install unpinned PPA repositories or execute raw shell tasks with sudo. If Vulcan executes that, we have built a remote code execution engine with an enterprise banner.

**Andrej Karpathy:**
And from the AI perspective, the idea that an LLM should "author playbooks" on the fly is an architectural hallucination. Software 2.0 does not mean throwing away Software 1.0 rigor. When an LLM generates free-form YAML or HCL, the probability of semantic failure, syntax error, or unvalidated flag injection approaches 1.0 at scale. The LLM's role in Vulcan is strictly bounded: **Intent Compilation**. Given a natural language utterance, extract structured, typed slots for an already-reviewed, deterministic catalog item.

**Alex Xu:**
So how do we reconcile the operator's desire to leverage the vast open-source ecosystem without violating INV-1? We must physically and logically segregate the **Candidate Store** from the **Active Catalog**. In memory and in database storage, candidates must be completely invisible to the runtime intent resolver and the job execution dispatcher. If an operator asks *"run load balancer"*, the search engine must never even see a candidate module.

**Uncle Bob:**
Exactly. And that boundary must not be a mere convention or an `if` statement in a controller. It must be an immutable domain invariant. Look at what we put into `CatalogItem`:
1. A `curation_status: CurationStatus` enum (`CANDIDATE`, `DRAFTED_PR`, `CURATED`, `REJECTED`).
2. A deterministic method `can_execute() -> bool` that returns `True` **if and only if** `curation_status == CurationStatus.CURATED`.
3. In `BaseJobRunner.run`, Step 0—before target locks are touched, before sandboxes are spun up—asserts `can_execute()`. If false, it synchronously commits an `EXEC_BLOCKED` record to the Merkle audit ledger and raises `PolicyViolationError`.
4. In `POST /api/v1/jobs`, submitting any item that is not curated returns `HTTP 403 Forbidden`. That is what I call a non-bypassable steel cage.

---

### DEBATE SESSION 2: THE CURATION GATE & PR-DRAFTING WORKFLOW

**Jordan Walke:**
Let's talk about the human in the loop. In traditional IT, onboarding a third-party Terraform module into an enterprise takes 6 weeks of Jira tickets, vendor meetings, and manual code reviews. Engineers get frustrated and bypass the system. If we want operators to respect the steel cage, the **Curation Gate** must have zero friction.

**Platform Lead:**
Zero friction cannot mean zero security. Here is the non-negotiable enterprise onboarding checklist:
1. **Provenance Verification:** Upstream repository URL, tag, author, and download count.
2. **Cryptographic Checksum:** Download the release tarball and compute its SHA-256 digest so we can prove the code hasn't been modified in transit or altered post-publication.
3. **Static Security Scanning:** Run `tfsec` and `Checkov` on Terraform modules, and `ansible-lint` and secret scanners on Ansible roles.
4. **Internal Vendoring:** The code must be mirrored into the corporate Git repository (`git@github.internal.bank.com:automation/catalog-modules.git`). It must **never** be referenced via an external URL at runtime.
5. **Immutable Commit Pinning:** The catalog item must bind to an immutable 40-character Git commit SHA (`^[0-9a-f]{40}$`), never a floating branch or mutable tag like `v1.0.0` or `main`.

**Jordan Walke:**
That’s why the **Registry Crawler Agent** acts as an administrative co-pilot! When an operator finds a promising module in the Candidate Store, they don't do manual Git archaeology. They click **"Draft Vendoring PR"**.
The agent:
- Calculates the upstream tarball SHA-256 digest.
- Creates an isolated branch (e.g. `curation/tf-google-lb-http-v14.2.0`).
- Generates the onboarding README diff and compliance checklist.
- Sets the status to `DRAFTED_PR`.

**Uncle Bob:**
And then comes the constitutional moment: **The Human Approval Gate**. An approving platform engineer reviews the PR in internal Git. Once satisfied, they invoke `approve_candidate`:
- They provide their corporate ID (`approver_id`).
- They provide the internal Git repository URL.
- They provide the reviewed 40-character hex commit SHA.
Only then does the service flip `curation_status` to `CURATED` and register it into the active catalog.

---

### DEBATE SESSION 3: SCHEMA TRANSFORMATION & THE NO-GUESSING POLICY (RULE 2)

**Andrej Karpathy:**
Let's address one of the most insidious bugs in cloud automation: **Default Value Injection**. In Terraform modules, authors frequently specify defaults:
```hcl
variable "cidr_block" {
  type    = string
  default = "10.0.0.0/16"
}
```
If an operator says *"provision a VPC for the retail payment gateway in production"*, what should the platform do?

**Alex Xu:**
A naive LLM system reads the schema, sees `default = "10.0.0.0/16"`, silently fills it in, and runs the stack. In banking, deploying a payment gateway on an overlapping CIDR block will take down the inter-bank routing tables!

**Andrej Karpathy:**
Exactly! That is why we formulated **Rule 2: The Suggested Defaults Policy**:
> *Upstream registry defaults are advisory UI suggestions. They are NEVER silent pre-fills.*

In our `TerraformTypeTransformer`:
1. Variable definitions are compiled into typed `ParamSpec` contracts (`string`, `integer`, `bool`, `list`, `map`).
2. Upstream defaults are stored separately in `provenance["suggested_defaults"]`.
3. In `IntentResolver`, parameters are extracted **only if the operator explicitly provided them in natural language**.
4. If a required operational slot is missing, the resolver strictly returns `NEEDS_INPUT`, rendering slot-filling chips in the UI.
5. The UI shows the suggested default as a placeholder or keyboard shortcut pill (e.g. `[Use Suggested: 10.0.0.0/16]`), but the human must actively confirm it!

**Uncle Bob:**
This preserves the core principle: **The AI never guesses.** In our scale benchmark across 10,000 real-world schemas, we measured 0% default leakage. If the user didn't say it, the machine doesn't execute it.

---

### DEBATE SESSION 4: LICENSE POLICIES & THE BUSL QUARANTINE GATE

**Platform Lead:**
We cannot talk about the Terraform Registry without addressing the elephant in the room: **HashiCorp’s Business Source License (BUSL-1.1)** and similar source-available licenses (SSPL). In a financial enterprise, deploying software covered by non-permissive or non-OSI licenses exposes the institution to legal copyright risk and vendor auditing.

**Uncle Bob:**
So the License Gate must be a first-class citizen in the Crawler Agent, not an afterthought.

**Platform Lead:**
We established an explicit policy whitelist:
- **`ALLOWED_LICENSES` (Permissive):** `MIT`, `Apache-2.0`, `MPL-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`.
- **`FLAGGED_LICENSES` (Quarantined):** `BUSL-1.1`, `SSPL`, `GPL-3.0` (in specific linking contexts), `PROPRIETARY`, `UNKNOWN`.

**Jordan Walke:**
In the UI, any module carrying a `FLAGGED_LICENSE` gets a glowing rose badge: `<AlertTriangle /> BUSL-1.1 RESTRICTED`. The Curation Gate service actively **refuses approval** if the license is non-compliant, directing the operator to the OpenTofu registry or an open-source MPL-2.0 fork instead.

---

### DEBATE SESSION 5: COMPOSITE STACK ARTIFACTS (`REG-05`)

**Andrej Karpathy:**
Let's resolve the user's scenario: *"I want to provision complete infrastructure on AWS (VPC + EKS + RDS)."*
How does Vulcan execute a multi-module architecture without the LLM authoring glue code?

**Alex Xu:**
This is the **Stack Composition Engine (`REG-05`)**. In modern infrastructure, you don't execute isolated modules in a vacuum; you execute **Landing Zones**. A Landing Zone is a composition of vetted modules:
- Module A: `terraform-aws-vpc`
- Module B: `terraform-aws-eks`
- Module C: `terraform-aws-rds`

**Uncle Bob:**
And how is that composition stored? Not in the LLM's prompt! It is stored as a **Composite CatalogItem**:
- Identifier: `aws.enterprise.landing_zone.vpc_eks_rds`
- Git Repo: `git@github.internal.bank.com:automation/catalog-modules.git`
- Path: `stacks/aws-banking-landing-zone/`
- Bound Commit SHA: Immutable 40-character hex.
- Input Schema: Unified `ParamSpec` declaring VPC CIDR, cluster node count, and database instance class.

**Andrej Karpathy:**
Now observe what happens when an operator types:
*"Provision AWS landing zone in us-east-1 with 10 EKS nodes and postgres"*
1. The `IntentResolver` vectors match against `aws.enterprise.landing_zone.vpc_eks_rds`.
2. It extracts `region: us-east-1`, `node_count: 10`, `engine: postgres`.
3. It detects missing `vpc_cidr` and `environment` $\rightarrow$ `status: NEEDS_INPUT`.
4. Operator completes the slots $\rightarrow$ `terraform plan` produces an exact resource diff.
5. The Maker-Checker approval deck reviews the diff.
6. Execution proceeds through the sandboxed runner.
Notice: **Zero internet code was touched. Zero HCL was written by an LLM.** The operator achieved total flexibility; the bank retained total governance.

---

### CONSOLIDATED CURATION OPPORTUNITY REGISTER (REG-XX)

| ID | Name | Problem Killed | Source Persona | Priority | Phase |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REG-01** | Registry Crawler Agent & Candidate Store | Eliminates manual module entry; crawls Galaxy & TF Registry into isolated candidate store. | Alex Xu | **P0** | Phase 1 (Safety) |
| **REG-02** | Curation Gate & PR-Drafting Workflow | Enforces human review; auto-generates vendoring PRs with SHA-256 tarball digests & security checklists. | Platform Lead | **P0** | Phase 1 (Safety) |
| **REG-03** | Typed Schema Transformer with Advisory Hints | Compiles HCL/YAML variables to `ParamSpec`; prevents silent default guessing (D1 / CHAT-10 / Rule 2). | Andrej Karpathy | **P0** | Phase 1 (Safety) |
| **REG-04** | Security & Compliance Scan Pipeline | Runs `tfsec`, `Checkov`, and `ansible-lint` on candidates prior to corporate Git admission. | Platform Lead | **P1** | Phase 2 (Infra) |
| **REG-05** | Composite Stack Artifacts | Enables multi-module landing zones (VPC+EKS+RDS) without LLM code authoring at runtime. | Uncle Bob / Alex Xu | **P0** | Phase 1 (Safety) |
| **REG-06** | Upstream Freshness & Semantic Drift Monitor | Tracks upstream releases and CVEs; alerts operators without ever auto-upgrading production code. | Platform Lead | **P2** | Phase 6 (Hardening) |
| **REG-07** | License Policy & BUSL Quarantine Gate | Detects non-permissive or proprietary licenses (`BUSL-1.1`, `SSPL`) and blocks approval. | Platform Lead | **P0** | Phase 1 (Safety) |
| **REG-08** | Operator Console Curation Deck (`/curation`) | Gives operators a high-tech UI to explore candidates, triage licenses, and execute 1-click PR/Approval. | Jordan Walke | **P0** | Phase 5 (Console) |

---

### MEASUREMENT & VERIFICATION PLAN

| Metric | Target | Instrument | Enforcement Gate |
| :--- | :--- | :--- | :--- |
| **Candidate Execution Refusal Rate** | **100.0%** (0 executions permitted) | `tests/test_curation_gate.py:test_runner_blocks_candidate_execution_inv1` | CI Gate (Blocking) |
| **Default Guessing Rate (Rule 2 / D1)** | **0.0%** (Zero silent pre-fills) | `backend/scripts/benchmark_catalog_scale.py` | Adversarial Eval Gate |
| **License Quarantine Accuracy** | **100.0%** (All BUSL/SSPL flagged) | `tests/test_curation_gate.py:test_license_gate_flags_and_blocks_busl` | Curation Gate Service |
| **Candidate Store Isolation Latency** | **< 5 ms** (Candidates excluded from runtime) | `tests/test_ai_reasoning_evals.py` | Intent Resolver Benchmark |
| **Git SHA Binding Invariant** | **100.0%** (40-char hex mandatory) | `tests/test_domain_invariants.py` | Pydantic Schema Invariant |

---

### GUARDRAILS: WHAT THE CURATION SUBSYSTEM MUST NEVER DO

1. **NEVER execute uncurated candidate code:** A candidate module must never be passed to `ansible-runner`, `terraform apply`, or any execution subprocess under any circumstance.
2. **NEVER allow runtime external downloads:** The execution environment must run hermetically without internet access to `registry.terraform.io`, `galaxy.ansible.com`, or GitHub.
3. **NEVER allow the LLM to generate executable playbooks:** The LLM maps intent to parameters of reviewed catalog items. It never authors dynamic automation code.
4. **NEVER pre-fill unconfirmed defaults:** Schema defaults are advisory hints for the UI; `IntentResolver` must fail-closed to `NEEDS_INPUT` if parameters are missing.
5. **NEVER promote a candidate without an internal Git SHA:** Curation promotion strictly demands an internal repository URL and a verified 40-character commit SHA.
6. **NEVER auto-approve based on upstream star count:** Upstream metrics (stars, downloads) are informational signals; they are never a substitute for human security review.

---

### DEFINITION OF DONE

An item in the Curation Register is marked **DONE** if and only if:
1. **Domain Isolation:** Candidates cannot execute; attempts produce `PolicyViolationError` and write `EXEC_BLOCKED` to the Merkle audit ledger.
2. **Deterministic Tests:** Invariant unit tests pass verifying candidate blocking, license gating, PR drafting, and SHA binding.
3. **Ergonomic UI:** The feature is represented in the Operator Console (`/curation`) with clear status indicators and interactive modals.
4. **Zero Regressions:** The full backend and frontend test suites pass with 100% clean green execution.
