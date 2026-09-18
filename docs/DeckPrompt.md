You are an elite Enterprise Tech Presentation Designer. Generate a high-impact, 5-slide hackathon pitch deck inside this presentation template for "Project Vulcan". 

Design Rules:
- Create EXACTLY 5 slides following the numbered outline below.
- Avoid generic bullet dumps: use 2-column split comparisons, process flows, bold lead-ins, and structured cards.
- Tone: High-stakes, authoritative enterprise infrastructure engineering.
- Insert the word-for-word speaker notes into the PowerPoint Presenter Notes section of each slide.

---

### SLIDE 1: Title & Executive Hook
- Slide Title: PROJECT VULCAN
- Subtitle: The Autonomous AI Infrastructure Control Plane That Never Lies
- Category Tag: GCCHackathon 2026 · Team 55 · Enterprise AI Governance & Autonomous SRE
- Layout: 3 Horizontal Highlight Cards
  1. Card 1 [Stop Icon]: "Zero Synthetic Fallbacks" — Never fakes confidence with static scores or fake health checks; fails closed safely.
  2. Card 2 [Dual-User Icon]: "Enforced Maker-Checker" — Mandates Four-Eyes dual control and ServiceNow change tickets for all Tier-1 changes.
  3. Card 3 [Chain Icon]: "Cryptographic Provenance" — Immutable SHA-256 Merkle tree execution proof verified live on /api/v1/health.
- Bottom Line: Built for SREs, Platform Engineers, Cloud SecOps, and Compliance Teams.
- Speaker Notes:
"Judges, almost every autonomous AI DevOps agent you've seen is a production hazard. They wrap an LLM around bash commands, hallucinate non-existent flags, and return hardcoded 95% confidence scores while production silently burns. That's why Tier-1 institutions strictly forbid AI in production. We built Vulcan to solve this fundamental paradox. Vulcan is an Autonomous AI Infrastructure Control Plane engineered with zero synthetic fallbacks, mandatory Maker-Checker dual control, and cryptographic audit proofs. We mathematically guarantee it never executes without verified policy, human authorization, and deterministic proof."

---

### SLIDE 2: The Big Question: What Problem Are We Solving?
- Slide Title: What Problem Are We Solving?
- Subtitle: The Uncomfortable Tension Between Manual Slowness and AI Hallucinations
- Layout: 2-Column Side-by-Side Comparison + Bottom Banner
- Left Column [Red/Danger Card]: "The 3 Production Killers"
  • The Fatal Runbook Trap: 70% of enterprise outages stem from manual typos, copy-paste slips, and 3:00 AM human fatigue.
  • The AI Hallucination Danger: Generic LLMs hallucinate destructive flags (rm -rf /, dropping tables) with 100% false confidence.
  • The Compliance Chasm: Terminal scripts lack immutable audit trails, violating SOX, SOC2, and PCI-DSS separation-of-duties mandates.
- Right Column [Cyan/Solution Card]: "The Vulcan Intelligent Gatekeeper"
  • Core Idea: Vulcan sits as a fail-closed control plane between engineers and production fleets.
  • Conversational Slot-Filling: Extracts parameters and prompts interactively via UI launch cards instead of crashing.
  • Maker-Checker Dual Control: Halts high-risk operations until an independent Technical Lead signs off.
  • Zero-Mock Refusal: Instantly refuses prompt injections and ungrounded commands.
- Bottom Callout Banner: "Enterprise Reusability: Hexagonal adapter pattern plugs directly into ServiceNow, CyberArk, Ansible, AWS, and Kubernetes without rewriting enterprise infrastructure."
- Speaker Notes:
"What problem are we actually solving? In enterprise operations, there are two ways to fail. First, human runbooks: an engineer wakes up at 2 AM, copies commands from a wiki, fat-fingers a variable, and takes down checkout for 4 hours. That is how 70% of outages happen. Second, naive AI agents: you give an LLM an API key and ask it to fix a database. It invents parameters, bypasses your change-management window, drops a table, and prints 'Success!' with 99% confidence. Vulcan solves both. It sits as an intelligent, fail-closed gatekeeper between operators and machines. And because Vulcan uses a clean hexagonal architecture, it reuses your existing investments: your Ansible playbooks, your CyberArk vaults, and your ServiceNow workflows without rewriting a single line."

---

### SLIDE 3: How Does It Work? (Lifecycle & Architecture)
- Slide Title: How Does It Work: The 5-Stage Governed Pipeline
- Subtitle: Deterministic Execution Through 5 Unbreakable Safety Gates
- Layout: 5-Step Horizontal Process Flow + Comparison Table Below
- Step Flow:
  1. [INTENT]: Conversational slot-filling; parses typed Pydantic models; asks for missing fields in chat.
  2. [DISCOVER]: Hybrid RRF search (Dense Cosine + Sparse BM25) across 120 curated production playbooks.
  3. [GUARD]: Blast-radius calculation; validates ServiceNow CHG tickets; halts for Lead Bob sign-off.
  4. [EXECUTE]: Scoped capability tokens issued, cryptographically locked to exact Git commit SHAs.
  5. [VERIFY]: Probes live OS post-conditions (kpatch, ports, disk); commits proof to SHA-256 Merkle tree.
- Comparison Table:
  • Execution Safety: Naive Agents = Unbounded shell subprocess | Vulcan = Pinned, pre-validated YAML playbooks
  • Approval Workflow: Naive Agents = Agent acts as root | Vulcan = Enforced Four-Eyes Maker-Checker dual control
  • Truth Verification: Naive Agents = Believes LLM self-report | Vulcan = Independent live OS state probes + Merkle ledger
- Speaker Notes:
"Let's look under the hood. Vulcan executes through five deterministic stages: Stage 1 is Intent: The engineer speaks naturally. Vulcan extracts parameters into typed models. If you forgot the port or host, it doesn't crash—it opens an interactive card in the chat and asks for it. Stage 2 is Discover: We run a hybrid semantic search across our catalog of 120 battle-tested playbooks, refusing ungrounded requests immediately. Stage 3 is Guard: This is our secret weapon. If an action is High-Risk—like a kernel patch or database migration—Vulcan halts. It validates the change ticket and requires a physical four-eyes sign-off from an authorized technical lead. Stage 4 is Execute: The executor receives a cryptographically signed capability token locked to the exact SHA hash of the playbook. Stage 5 is Verify: We never trust the LLM to self-grade. Vulcan fires live OS probes to verify the desired state is achieved, and commits the evidence into an immutable SHA-256 Merkle ledger. Competitors build chatbots that type in bash. We built a zero-trust control plane."

---

### SLIDE 4: Business Value, Relatable Scenario & Honest Scope
- Slide Title: Real-World Business Value & Demonstrated Impact
- Subtitle: The 2:00 AM Kernel Zero-Day Emergency (CVE-2025-3912 on rhel-app-01)
- Layout: Top Before/After Scenario Box + 2-Column Scope Matrix Below
- Top Scenario Card:
  • Without Vulcan (Manual Runbook): 2 AM wake-up, manual SSH, parameter typo in kernel flags, rebooted active database VIP. Outcome: 4 hours downtime, $350,000 lost revenue, failed SOC2 audit.
  • With Vulcan (Governed Control Plane): Single chat request, slots extracted, routed to Lead Bob for one-click approval, live kpatch applied without reboot. Outcome: Resolved in 90 seconds, 0 downtime, $0 lost, 100% auditable.
- Bottom 2-Column Matrix:
  • Column 1 [Live Software]: Built & Demonstrated Today: Multi-turn Copilot with interactive slot launch cards, Maker-Checker role separation (Alice -> Bob), AgentOS 8-stage compiler, 120 production playbooks, 50-scenario benchmark with 0.0% false-success rate, SHA-256 Merkle ledger live on /api/v1/health.
  • Column 2 [Roadmap]: Described & Future Horizon: Closed-loop Datadog/Prometheus alert auto-remediation, air-gapped edge cluster dispatch, on-prem 7B SLM model distillation.
- Key Metrics Bar: 98% MTTR Reduction | 0% Unauthorized Changes | 100% Audit Readiness
- Speaker Notes:
"Let's translate this into cold, hard business reality with a scenario every engineer in this room dreads: The 2 AM Kernel Zero-Day. A critical CVE hits at 2 AM on a Friday night. A tired engineer SSH'es into rhel-app-01, copies a patch command, makes a syntax error, and reboots the active database VIP. That mistake costs $350,000 in lost transactions and triggers a brutal regulatory audit. Now watch what happens with Vulcan: The engineer chats: 'Patch RHEL 9 kernel CVE-2025-3912 on rhel-app-01'. Vulcan parses the parameters, flags the high risk, pulls historical failure baselines, and sends an approval card to Lead Bob's phone. Bob approves with one click. Vulcan applies the live kernel patch with zero downtime, verifies the kernel status, and signs the Merkle ledger. Total elapsed time: 90 seconds. Zero downtime. Zero revenue lost. And let's be completely transparent about what we built: Everything you see today is live code running right now. On our roadmap, we're expanding into autonomous Datadog alert triggers and air-gapped edge models."

---

### SLIDE 5: Conclusion & Live Verification
- Slide Title: VULCAN: The Infrastructure AI You Can Actually Trust
- Hero Quote: "Infrastructure is binary. Your AI must be too."
- Layout: 3 Live Interactive Access Cards
  1. Card 1 [Web Icon]: "Local Web Console" — http://localhost:3000 (Interactive Copilot & Generator)
  2. Card 2 [Cloud Icon]: "Public Judge Access" — https://odd-bobcats-post.loca.lt (Live tunnel endpoint)
  3. Card 3 [Shield Icon]: "Merkle Ledger API" — :8000/api/v1/health (audit_chain_valid: true)
- Footer: Team 55 · GCCHackathon 2026 · Open for Questions & Live Interactive Testing
- Speaker Notes:
"In summary: Vulcan transforms enterprise infrastructure from slow manual runbooks into fast, verifiable automation—without ever compromising safety or governance. Our backend is live, our frontend is running, and our public evaluator tunnel is open. We invite you to throw your hardest prompts, your missing parameters, and your adversarial injections at Vulcan Copilot right now. Thank you, and we're ready for your questions!"
