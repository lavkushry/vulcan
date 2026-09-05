# BUSINESS REQUIREMENTS DOCUMENT (BRD)

**PROJECT NAME:** Enterprise Automation Control Plane (Project Vulcan / Platform OS)  
**ORGANIZATION:** Enterprise Technology & Platform Engineering (Banking Infrastructure)  
**DOCUMENT VERSION:** 1.0 — Final Draft  
**STATUS:** Ready for Executive Review & Architecture Board Sign-Off  
**COMPLIANCE CLASSIFICATION:** Highly Confidential — Internal Banking Standard  

---

## DOCUMENT REVISION & APPROVAL CONTROL

| Version | Date | Author | Description / Change Rationale | Approver Sign-off |
| :--- | :--- | :--- | :--- | :--- |
| **1.0** | September 2026 | Automation & SRE Core Team | Comprehensive BRD covering all business, regulatory, architectural, and operational scenarios. | Head of Enterprise Architecture, CISO Lead, Infrastructure Director |

---

## 1. EXECUTIVE SUMMARY & STRATEGIC INTENT

### 1.1 Executive Overview
PNC Bank maintains an extensive portfolio of over **1,000+ battle-tested Ansible playbooks, Terraform modules, and operational scripts** across distributed teams. However, the bank lacks a unified, governed, and intelligent platform to discover, parameterize, authorize, and execute these assets.

Today, engineers interact with automation through fragmented command-line interfaces (CLI) on bastion hosts, manual parameter formatting, untracked chat approvals, and disjointed ServiceNow tickets. Furthermore, long-running operations (e.g., 10–30 minute Terraform rollouts, network firmware upgrades, and database resizes) force engineers to actively babysit terminal screens, causing context switching, cognitive fatigue, and severe productivity bleed.

The **Enterprise Automation Control Plane** is a centralized, AI-native self-service platform designed from first principles. It indexes 1,000+ automation assets as callable primitives, enforces strict banking guardrails (Maker-Checker, ServiceNow ticket synchronization, CyberArk secret isolation), handles complex data inputs (including JSON schemas and 10GB binary artifacts), eliminates execution babysitting through active asynchronous observability, and leverages AI for pre-flight synthesis, diff summarization, and root-cause failure diagnostics.

### 1.2 Core Architectural Philosophy
> **"The AI is the Intelligent Dispatcher & SRE Co-Pilot inside a Deterministic Steel Cage."**  
> The system operates under strict Separation of Concerns:
> 1. **Intelligence Plane (LLM / Agent):** Handles discovery, intent-to-schema parameter extraction, ticket drafting, diff summarization, and log failure diagnostics.
> 2. **Control & Policy Plane (Deterministic Code):** Enforces Maker-Checker (Separation of Duties), ServiceNow ticket states, maintenance window validation, parameter regex/enums, and immutable audit writes.
> 3. **Execution Plane (Ephemeral Sandboxes):** Executes pre-vetted Ansible playbooks and Terraform plans via isolated worker pods. Secrets are injected at runtime from CyberArk and wiped clean immediately upon completion.

---

## 2. BUSINESS PROBLEM STATEMENT & FINANCIAL IMPACT

### 2.1 The Four Core Business Pains

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             CURRENT OPERATIONAL REALITY                          │
│                                                                                  │
│   [ 1,000+ Git Playbooks ]          [ Fragmented Tickets ]    [ Terminal Babysitting ]
│   • Undocumented syntax             • Manual copy-pasting     • 10-30m log watching  │
│   • Siloed team knowledge           • Unverified approvals    • Missing post-checks  │
│   • Terrified to run old scripts    • Untracked chat logs     • Silent failure risks │
│                 │                             │                         │        │
│                 └─────────────────────────────┼─────────────────────────┘        │
│                                               ▼                                  │
│                 ┌──────────────────────────────────────────────┐                 │
│                 │ $2.28M Annual Lost Engineering Productivity  │                 │
│                 │ + $1.5M-$3M Vendor Software Licensing Tax    │                 │
│                 │ + Severe OCC / Fed Regulatory Audit Gaps     │                 │
│                 └──────────────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────────────────┘
```

1. **The 1,000-Playbook Discovery & Maintenance Tax:** Engineers waste 30–60 minutes per incident searching across repositories, guessing parameters, and reading outdated READMEs. Playbooks suffer from code rot, leading to duplicate implementations and fear of executing unfamiliar automation.
2. **The "Babysitting" Tax (Tethered Engineers):** Infrastructure rollouts taking 10 to 30 minutes require active monitoring because engineers cannot trust automation to fail gracefully or verify application health.
3. **Governance Theater & Audit Exposure:** ServiceNow Change Requests (CHGs) are filled manually and have zero technical binding to the command executed in the terminal. Audit reconstruction for OCC, Federal Reserve, and SOX takes weeks of log archaeology.
4. **The Commercial Software Licensing Trap:** Buying proprietary enterprise suites (Red Hat AAP + Terraform Enterprise) incurs **$1.5M–$3M+ in annual recurring license costs**, requires multi-year rollout timelines, and maintains isolated tool silos.

### 2.2 Quantified Financial Business Case (Baseline: 75 Engineers)

| Operational Waste Area | Current State Impact | Annual Direct Cost ($120/hr loaded) |
| :--- | :--- | :--- |
| **Playbook Lookup & Parameter Guessing** | 20 min/run $\times$ 300 runs/wk = 100 hrs/wk | **$624,000** |
| **Active Execution Babysitting (10–30 min)** | 15 min/run $\times$ 300 runs/wk = 75 hrs/wk | **$468,000** |
| **ServiceNow Ticket Drafting & Chat Approvals** | 25 min/run $\times$ 300 runs/wk = 125 hrs/wk | **$780,000** |
| **Manual Debugging of Cryptic Failure Logs** | 45 min/failure $\times$ 45 failures/wk = 33.7 hrs/wk | **$210,000** |
| **Audit Preparation & Compliance Archaeology** | 80 hrs/quarter across teams = 6.2 hrs/wk | **$38,400** |
| **Software License Cost Avoidance (AAP + TFE)** | Commercial license fees avoided per year | **$1,800,000** |
| **TOTAL ANNUAL QUANTIFIED VALUE** | **Direct Capacity & Cost Savings** | **$3,920,400 / year** |

---

## 3. STAKEHOLDER ECOSYSTEM & USER PERSONAS

| Persona | Role | Key Objectives & Pain Points |
| :--- | :--- | :--- |
| **Persona A: Requesting Engineer (DevOps/SRE)** | Executes infrastructure provisioning, patching, and deployments. | Wants zero CLI syntax friction, auto-filled parameters from Jira/ServiceNow, and the ability to submit a job and walk away without babysitting. |
| **Persona B: Approving Lead (Checker)** | Team Lead, Architect, or CAB Approver. | Needs an executive diff summary (not 2,000 lines of raw code), clear blast radius, and one-tap approval without logging into slow portals. |
| **Persona C: Compliance & Audit Officer** | Internal Audit, Risk, SOX, Regulators (OCC/Fed). | Requires mathematical proof linking Requester $\rightarrow$ Approver $\rightarrow$ ServiceNow CHG $\rightarrow$ Raw Git Commit $\rightarrow$ Immutable Execution Log. |
| **Persona D: Executive Leadership (VP/Director)** | Engineering budget holder and risk owner. | Demands elimination of multi-million dollar vendor licensing, measurable MTTR reduction, and zero production outages caused by human error. |

---

## 4. DETAILED BUSINESS REQUIREMENTS & SCENARIOS

```
                                  BUSINESS USE CASE MATRIX
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  UC-01: Catalog Ingestion (1,000+ Items)      │  UC-06: Terraform Plan-Diff-Apply Gate  │
│  UC-02: Multi-Source Input Extraction         │  UC-07: Asynchronous Observability     │
│  UC-03: Complex JSON Configuration & Linting  │  UC-08: AI Failure Root-Cause Analysis  │
│  UC-04: Massive 10GB Artifact Streaming       │  UC-09: Semantic Health Verification    │
│  UC-05: Maker-Checker & ServiceNow Auto-Sync  │  UC-10: Immutable Audit & SIEM Export   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### USE CASE 1: Dynamic Catalog Ingestion & Semantic Discovery
* **Business Requirement ID:** `BR-CAT-01`
* **Objective:** Enable a centralized, searchable catalog across 1,000+ playbooks and modules without manual form creation.

#### Detailed Scenario:
1. The platform's **GitSync Service** continuously monitors enterprise Git organizations (Bitbucket/GitHub).
2. It parses lightweight `metadata.yaml` or parses the playbook's native `vars_prompt` and comment headers.
3. The platform indexes all 1,000+ automations into a semantic vector space (Search Index).
4. An engineer enters the portal and types: *"Drain traffic from Dallas Datacenter cluster and rotate edge certs."*
5. The system performs semantic matching, ranks candidate playbooks, and returns the certified, peer-reviewed automation: `playbooks/f5_cluster_drain.yml`.
6. **Acceptance Criteria:**
   * Zero manual UI coding required when adding new playbooks to Git.
   * New playbooks committed to the default branch appear in the catalog within 60 seconds.
   * Unauthorized, unmerged, or experimental playbooks cannot be discovered or executed.

---

### USE CASE 2: Multi-Source Input Gathering & Dynamic Slot-Filling
* **Business Requirement ID:** `BR-INP-02`
* **Objective:** Eliminate parameter data entry errors, manual typing, and 1,000 static forms.

#### Detailed Scenario:
1. Playbooks define strict parameter schemas (types, enums, regex patterns, min/max).
2. **Extraction Sources:**
   * **Prompt:** Natural language input (*"Expand `/data` by 50GB on `pnc-db-01` in UAT"*).
   * **ServiceNow Integration:** User enters `CHG0098123`. The system calls the ServiceNow API and extracts the CI (`pnc-db-01`), Environment (`UAT`), and Size (`50GB`).
   * **CMDB Enrichment:** The system queries CMDB to resolve hostnames to IP addresses, subnets, and operating systems.
3. **Dynamic Slot-Filling (Missing Inputs):**
   * If a required field (e.g., `environment`) is missing, the AI **does not guess**.
   * It presents an interactive **Micro-Card** with targeted selectors (`[ DEV ] [ UAT ] [ PROD ]`).
4. **Deterministic Code Boundary:**
   * Parameters are validated via `Pydantic` code against strict regex patterns (e.g., hostname must match `^pnc-[a-z0-9-]+$`).
5. **Acceptance Criteria:**
   * If any required parameter fails regex or range checks, execution is blocked with actionable user feedback.
   * Zero hallucinated parameters allowed into the execution wrapper.

---

### USE CASE 3: Structured Configuration & JSON File Inputs
* **Business Requirement ID:** `BR-INP-03`
* **Objective:** Support complex configuration payloads, firewall rule arrays, and policy documents cleanly.

#### Detailed Scenario:
1. When a playbook requires a JSON configuration file (e.g., `firewall_rules.json` or `routing_policy.json`), the system supports three intake methods:
   * **Method A (Direct Upload/Paste):** Built-in web code editor with real-time JSON syntax and schema validation.
   * **Method B (AI Synthesis):** The user provides plain English intent (*"Allow 443 and 80 from 10.240.10.0/24"*), and the AI synthesizes the exact schema-compliant JSON file.
   * **Method C (GitOps Reference):** Direct pointer to a version-controlled JSON file in Git.
2. **Automated Secret Scanning Guard:**
   * Before ingestion, an automated scanner checks the JSON payload for accidental hardcoded passwords, tokens, or private keys.
   * If detected, the file is rejected immediately with an alert directing the user to CyberArk.
3. **Execution Delivery:**
   * The platform writes the validated JSON to an isolated sandbox file (`/runs/EXEC-XXXX/vars.json`, permissions `chmod 600`) and passes it to Ansible via `--cmdline "-e @vars.json"`.
4. **Acceptance Criteria:**
   * Accidental secret exposure in JSON files is structurally prevented.
   * Exact SHA256 hash of the applied JSON is attached to the audit log.

---

### USE CASE 4: Massive Binary & Large File Input Handling (10GB+ Payloads)
* **Business Requirement ID:** `BR-DAT-04`
* **Objective:** Handle large files (OS golden ISOs, database dumps, firmware images) without memory exhaustion or timeouts.

#### Detailed Scenario:
1. **Control Plane / Data Plane Decoupling:**
   * Large files **never** pass through the AI model, the API gateway memory, or chat interfaces.
2. **Path A: Enterprise Artifact Pointers (Standard):**
   * For existing binaries, the platform accepts an authenticated URI from JFrog Artifactory, internal S3, or SAN/NAS:
     `artifact_url: "s3://pnc-artifactory/isos/rhel-9.4-golden.iso"` + `sha256_checksum`.
   * The runner instructs the target host to stream the file directly over 10Gbps datacenter storage networks.
3. **Path B: Direct Chunked Multipart Upload:**
   * For local files, the web console requests a **Presigned S3/MinIO Multipart Upload URL**.
   * The browser uploads directly to object storage in parallel, resumable 50MB chunks.
   * Upon completion, the storage URI is passed to the execution wrapper.
4. **Acceptance Criteria:**
   * Zero memory bloat or HTTP request timeouts on the platform backend.
   * File integrity verified via SHA256 checksum comparison before playbook execution.

---

### USE CASE 5: Multi-Stage Governance, Maker-Checker & ServiceNow Lifecycle
* **Business Requirement ID:** `BR-GOV-05`
* **Objective:** Enforce banking-grade change management, dual control, and automated ServiceNow ticket management.

#### Detailed Scenario:

```
[Request Submitted] ──▶ [Policy Engine Evaluates Risk]
                                  │
                 ┌────────────────┴────────────────┐
                 ▼ (Low/Dev)                       ▼ (High/Prod)
         [Peer Notification]             [ServiceNow Enforcement]
                 │                                 │
                 │               ┌─────────────────┴─────────────────┐
                 │               ▼ (Ticket Exists)                   ▼ (No Ticket)
                 │         [Validate Status]                 [Auto-Draft CHG via API]
                 │               │                                   │
                 └───────────────┼───────────────────────────────────┘
                                 ▼
                    [Maker-Checker Gate: Teams / Web]
                    • Requester != Approver (Hard Rule)
                    • Active Change Window Check
                                 │
                         ┌───────┴───────┐
                         ▼               ▼
                    [APPROVED]      [REJECTED / 15-min TIMEOUT]
                         │               │
                         ▼               ▼
                 [Execute & Log]  [Fail-Closed Terminal]
```

1. **ServiceNow Auto-Creation:**
   * For production runs without a ticket, the AI generates the complete Change Request via REST API: Implementation Plan, Test Plan, Rollback Plan, Risk Assessment, and CI mapping.
2. **Maker-Checker Enforcement (Four-Eyes Principle):**
   * The system strictly blocks self-approval: `Requester_ID != Approver_ID`.
3. **Maintenance Window Verification:**
   * The platform cross-references the current time against the ServiceNow approved window. Execution is locked until the window opens.
4. **Fail-Closed Timeout:**
   * Approvals expire after 15 minutes of silence, resolving as an automatic denial.
5. **Acceptance Criteria:**
   * 100% of production runs bound to an approved ServiceNow CHG.
   * Work Notes and status transitions (`Scheduled` $\rightarrow$ `In Progress` $\rightarrow$ `Closed Complete`) synchronized in real time with bidirectional links.

---

### USE CASE 6: Multi-Engine Execution & Terraform Plan-Diff-Apply Lifecycle
* **Business Requirement ID:** `BR-EXE-06`
* **Objective:** Provide a unified control plane across Ansible, Terraform/OpenTofu, and scripts.

#### Detailed Scenario:
1. **The Terraform Lifecycle:**
   * Step 1: Runner executes `terraform plan -out=tfplan.binary`.
   * Step 2: Engine parses binary plan into structured JSON (`terraform show -json`).
   * Step 3: AI evaluates diff against policy rules (checks for zero deletions, no open security groups).
   * Step 4: System generates an **Executive Diff Card** (`+3 to add, 0 to destroy`) with an interactive **[Approve Apply]** button.
   * Step 5: Upon approval, the runner applies the exact cached plan file.
2. **Acceptance Criteria:**
   * No `terraform apply` may run without an explicit, approved plan cache.
   * Ansible and Terraform telemetry unified in a single dashboard and audit format.

---

### USE CASE 7: Asynchronous Observability & Elimination of Babysitting
* **Business Requirement ID:** `BR-OBS-07`
* **Objective:** Enable engineers to submit long-running changes and disconnect immediately.

#### Detailed Scenario:
1. When execution begins, the job dispatches to a background container worker.
2. The engineer can safely close their laptop or navigate away.
3. **Live Streaming:** Real-time log events stream over WebSockets to the web console for users who choose to watch.
4. **Push Notifications:** The platform pushes notifications to MS Teams, Slack, or Email at key milestones:
   * Execution started (`EXEC-0091`).
   * Plan ready for review.
   * Execution succeeded or failed with direct log summary.
5. **Acceptance Criteria:**
   * Zero active terminal presence required during long-running automations.
   * Real-time notifications dispatched within $<5$ seconds of state transitions.

---

### USE CASE 8: AI-Powered Failure Diagnostics & Root-Cause Analysis
* **Business Requirement ID:** `BR-AIA-08`
* **Objective:** Eliminate manual log archaeology when automations fail mid-run.

#### Detailed Scenario:
1. A playbook fails at task 37 with a 300-line Python stack trace.
2. The AI diagnostic engine intercepts the failure:
   * Strips boilerplate traceback noise.
   * Correlates error text with known issue documentation and past run history.
   * Generates a concise **Root-Cause Diagnostic Report**:
     > *"Task `Mount NFS Share` failed on host `pnc-app-04`. Reason: Port 2049 unreachable. Root cause: Security group `sg-nfs-client` missing egress rule to storage subnet `10.20.4.0/24`."*
   * Recommends the specific remediation playbook or parameter fix.
3. **Acceptance Criteria:**
   * Diagnostic summary produced in $<10$ seconds after playbook termination.
   * AI diagnostics provided as recommendations only; no automated changes applied without human approval.

---

### USE CASE 9: Semantic Post-Execution Health Verification (Beyond Exit 0)
* **Business Requirement ID:** `BR-VER-09`
* **Objective:** Verify actual application and infrastructure health before declaring success.

#### Detailed Scenario:
1. Script exit code `0` is treated as a necessary, but insufficient, condition for success.
2. **Post-Flight Health Probing:**
   * Synthetic HTTP/gRPC health probe execution against endpoints.
   * TLS certificate validity check (verifying TLS 1.3 handshake and expiration date).
   * Telemetry check: Queries Splunk/Datadog to ensure error rates have not spiked within 2 minutes post-change.
3. **Automated Rollback Trigger:**
   * If health checks fail, the system prompts the engineer with a one-tap rollback playbook.
4. **Acceptance Criteria:**
   * A job is marked "Success" only after post-flight health verification passes.
   * Results recorded in the ServiceNow closure notes.

---

### USE CASE 10: Immutable Audit Logging & Regulatory Compliance
* **Business Requirement ID:** `BR-AUD-10`
* **Objective:** Satisfy OCC, Federal Reserve, and SOX requirements for traceability.

#### Detailed Scenario:
1. Every action generates an append-only, tamper-proof JSONL record keyed by an immutable `correlation_id` (`EXEC-XXXX`).
2. **Pre-Execution Write:** The audit record is committed to disk **before** the runner process launches (ensuring failed launches are recorded).
3. **Audit Data Contract:**
   * Requester SAML Identity & IP.
   * Approver SAML Identity & Timestamp.
   * ServiceNow Ticket ID & Validation State.
   * Git Commit Hash of the Playbook/Module.
   * Sanitized Input Parameters & SHA256 Checksums of JSON/Binary Files.
   * Raw Execution Output & Final Health Verification Metrics.
4. **SIEM Mirroring:** All audit records stream in real time to the enterprise SIEM (Splunk / Elastic / Kafka).
5. **Acceptance Criteria:**
   * Audit query latency under 10 seconds for any historical execution.
   * Mathematical proof of zero credentials present in any log or prompt.

---

## 5. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| NFR Category | Metric / Target | Enforcement Mechanism |
| :--- | :--- | :--- |
| **High Availability** | 99.95% Availability | Active-Active deployment across dual banking data centers. |
| **Execution Concurrency** | Minimum 50 concurrent runner jobs | Distributed worker fleet (Kubernetes Job pods / Celery worker pool). |
| **API Response Latency** | p95 $< 1.5$ seconds | Async FastAPI backend with Redis caching. |
| **AI Intent & Plan Latency**| p95 $< 4$ seconds | Optimized inference with streaming token responses. |
| **Credential Security** | **Zero plaintext credentials** | CyberArk PAM dynamic retrieval; injected strictly into runner memory; zero disk writes. |
| **Data Retention** | 7 Years Immutable Retention | WORM (Write Once, Read Many) compliant object storage for regulatory audit logs. |
| **Disaster Recovery** | RPO = 0, RTO $< 15$ minutes | State managed in clustered PostgreSQL with continuous WAL archiving. |

---

## 6. ENTERPRISE GOVERNANCE, THREAT MODEL & SAFETY (THE "STEEL CAGE")

```
                               THE STEEL CAGE ARCHITECTURE
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                        │
│   1. ALLOWLIST-ONLY EXECUTION                                                          │
│      The AI has zero capability to generate or execute arbitrary bash/python code.     │
│      It selects exclusively from version-controlled, PR-reviewed playbooks.           │
│                                                                                        │
│   2. STRUCTURAL CREDENTIAL ISOLATION                                                   │
│      Secrets live in CyberArk / Vault. The AI never sees passwords, keys, or tokens.   │
│      Secrets are injected directly into the runner environment at runtime.             │
│                                                                                        │
│   3. FAIL-CLOSED POLICY GATES                                                          │
│      Risk tiers, variable regex, and Maker-Checker rules are evaluated by code,       │
│      never by LLM self-reporting. 15-minute approval timeout auto-denies.              │
│                                                                                        │
│   4. PROMPT INJECTION RESISTANCE                                                       │
│      Adversarial inputs can at best select an existing allowlisted playbook with       │
│      valid schema variables. Confirmation echo, approval, and audit still trigger.     │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 90-DAY PHASED IMPLEMENTATION ROADMAP

```
Phase 1: Foundation & Staging PoC (Days 1 – 30)
├── Ingest Top 50 Ansible Playbooks into GitSync Catalog
├── Deploy Core FastAPI Backend + Redis Worker Engine
├── Implement Web Console with Live Log Streaming & Maker-Checker
└── Milestone: Live staging demo executing real changes with zero CLI interaction

Phase 2: Governance & Production Hardening (Days 31 – 60)
├── Integrate ServiceNow REST API (Bidirectional CHG validation & auto-creation)
├── Integrate CyberArk PAM credential injection
├── Implement Large File Handling (S3/Artifactory pointers) & JSON Schema Validator
└── Milestone: Production pilot with two pilot engineering teams

Phase 3: Multi-Engine Scale & AI Intelligence (Days 61 – 90)
├── Ingest Terraform Modules with Plan-Diff-Apply Two-Stage Gate
├── Deploy AI Diagnostic Engine for Automated Log Root-Cause Analysis
├── Complete SIEM Splunk audit streaming & conduct OCC/SOX compliance audit review
└── Milestone: Full enterprise rollout across all Technology teams
```

---

## 8. EXECUTIVE APPROVAL & SIGN-OFF

By signing below, the stakeholders endorse this Business Requirements Document as the definitive specification for the **Enterprise Automation Control Plane (Project Vulcan)**.

**Executive Sponsor:** ___________________________________  Date: ____________  
*(Director of Infrastructure & Enterprise Technology)*

**Architecture Review Board:** ____________________________  Date: ____________  
*(Head of Enterprise Architecture)*

**Information Security & Risk:** __________________________  Date: ____________  
*(Chief Information Security Officer Representative)*
