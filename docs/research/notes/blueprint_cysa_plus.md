# CompTIA CySA+ blueprint — CS0-004 (V4) (state as of 25 November 2026)

Researcher notes for the `cysa-plus` course. This is the syllabus that part-file
authors work from. Topic lists are paraphrased and regrouped from CompTIA's
public objectives document; they are not a copy of it. Explanatory glosses in
parentheses are the researcher's, not CompTIA's.

Source-quality legend (same as `cert_blueprints.md`):
- **[VENDOR]** = read this session on CompTIA's own page or the official objectives PDF.
- **[3P]** = third-party source only.
- **[RECALL]** = researcher's own knowledge, not opened this session.

## 1. Exam facts

**The current exam is CS0-004 (V4), not CS0-003.** CS0-004 launched on
23 June 2026. CS0-003 (V3) is still bookable but is the "retiring version".

| Fact | Value | Source |
|---|---|---|
| Certification | CompTIA Cybersecurity Analyst (CySA+) | [VENDOR] objectives PDF |
| Exam code / version | CS0-004, V4 | [VENDOR] V4 page; objectives PDF |
| Launch date | 23 June 2026 | [VENDOR] V4 page |
| Retirement of V4 | not stated on the page (CompTIA exams usually run about three years) | date not published; the three-year habit is [RECALL] |
| Number of questions | maximum of 85 | [VENDOR] V4 page; objectives PDF |
| Question types | multiple-choice and performance-based | [VENDOR] objectives PDF |
| Length | 165 minutes | [VENDOR] V4 page; objectives PDF |
| Passing score | 750 on a scale of 100-900 (a scaled score, not a percentage) | [VENDOR] V4 page; objectives PDF |
| Recommended experience | about 4 years hands-on as a SOC analyst (level 2) or vulnerability analyst; a recommendation, not a prerequisite | [VENDOR] objectives PDF |
| Languages | English at launch; French, Japanese, Spanish and Portuguese "coming soon" | [VENDOR] V4 page |
| Accreditation | ANAB, ISO 17024 | [VENDOR] objectives PDF |
| Previous version | CS0-003 (V3): English retires 22 December 2026, translations 23 March 2027 | [VENDOR] CySA+ landing page |

**Domains and weights** [VENDOR, objectives PDF v2.0 and V4 page agree]

| Domain | Weight | Objectives |
|---|---|---|
| 1.0 Security Operations | 34% | 1.1-1.6 |
| 2.0 Vulnerability Management | 26% | 2.1-2.4 |
| 3.0 Incident Response and Management | 24% | 3.1-3.3 |
| 4.0 Reporting and Communication | 16% | 4.1-4.2 |

15 objectives in all (6/4/3/2).

**Sources**
- CompTIA CySA+ landing page (V4 "New Version", V3 "Retiring Version" and V3 retirement dates): https://www.comptia.org/en-us/certifications/cybersecurity-analyst/
- CompTIA CySA+ V4 page (code, launch date, questions, minutes, passing score, languages, domain weights): https://www.comptia.org/en-eu/certifications/cybersecurity-analyst/v4/
- "CompTIA CySA+ CS0-004 V4 Certification Exam — Exam Objectives Document Version 2.0" (copyright 2025), PDF served from CompTIA's content host: https://lecbyo.files.cmp.optimizely.com/download/68b1eae88e5011f08868a275d699e612

**Unverified / caveats**
- The PDF was reached through a web search result, not through a link on the
  V4 page (the page fetch showed no objectives link; CompTIA normally gates the
  download behind a form). It carries CompTIA's title page, copyright and
  "Version 2.0", and its test details and weights match the V4 page exactly, so
  it is treated as [VENDOR]. Whether a later document version exists was not
  confirmed.
- No retirement date for CS0-004 is published.
- The split between multiple-choice and performance-based questions is not
  published.
- The objectives say their bulleted examples are not exhaustive: other related
  tools and tasks can appear on the exam.

**What changed from CS0-003** [RECALL for the V3 side — V3 objectives were not
opened this session; spot-check before relying on it]
- Weights: V3 was 33/30/20/17; V4 is 34/26/24/16 (vulnerability management
  down, incident response up). The four domain names are unchanged.
- New in V4: an AI objective (1.6); SASE, secrets management, device management
  (mobile/endpoint), EVTX and YAML file formats; threat-intelligence platforms
  by name (OTX, MISP, OpenCTI); UEBA/OpenUBA; EPSS next to CVSS; cloud
  assessment tools Trivy and Checkov; breach-and-attack-simulation tools
  (Atomic Red Team, Caldera); Nuclei; SAST/DAST/SAMM, SCA and SBOM under
  vulnerability management; cyber deception as a named topic.
- Much reduced or no longer listed by name in V4: the long web-attack list
  (XSS, CSRF, SSRF, overflows and so on) and its mitigations, OWASP Testing
  Guide / OSSTMM as framework bullets (both survive only in the acronym list),
  debuggers (GDB, Immunity), Pacu, Arachni, and BC/DR as IR bullets.
  Because the examples are "not exhaustive", web-attack recognition in tool
  output is still fair game under 2.2.

## 2. Domain 1 — Security Operations (34%)

### 1.1 Explain concepts related to system and network architecture in security operations
- **Logging**: ingestion (getting sources into the platform), source
  configuration (what is logged and at what level), integrity and security of
  logs, time synchronization, retention.
- **Operating systems**: system hardening; file structure and the critical
  files worth watching (configuration, credential and start-up locations);
  system processes (what normally runs).
- **Infrastructure / system architecture**: cloud native, virtualization,
  containerization, APIs.
- **Device management**: mobile, endpoint.
- **Network architecture**: Zero Trust network architecture / access (ZTNA),
  secure access service edge (SASE), hybrid cloud.
- **Identity and access management**: privileged access management (PAM),
  authentication and authorization methods, secrets management.
- **Encryption techniques** (listed without sub-bullets).
- **Data protection concepts** (listed without sub-bullets; acronym list
  includes DLP, PII, CHD, CASB).
- **Critical infrastructure**: operational technology (OT), industrial control
  systems (ICS), SCADA.

### 1.2 Given a scenario, analyze indicators of potential malicious activity
- **Network**: rogue devices, enumeration (scans and sweeps), anomalous
  activity (beaconing, odd volumes or peers), activity on unexpected ports.
- **Host**: resource consumption; unauthorized software; anomalous activity —
  suspicious or rogue processes, living-off-the-land binaries (LOLBins) and
  scripts, file system changes, data exfiltration.
- **Unauthorized configuration** (changes nobody approved).
- **Application**: service disruption, anomalous activity.
- **Cloud**: anomalous activity, resource compromise.
- **Social engineering**: typosquatting, URL shorteners.
- **Identity**: IAM account compromise, unauthorized access, impossible travel.
- **Email**: business email compromise (BEC). (Acronym list adds SPF, DKIM,
  DMARC.)

### 1.3 Given a scenario, use tools to determine malicious activity
- **Decoding / parsing**: CyberChef.
- **Packet analysis**: Wireshark, tcpdump, Snort, Suricata, Zeek.
- **Log analysis**: SIEM.
- **Threat-intelligence platforms**: Open Threat Exchange (OTX), MISP, OpenCTI.
- **Endpoint security**: EDR and XDR; mobile device management (MDM).
- **Domain and IP reputation**: WHOIS, AbuseIPDB, geolocation by IP (GeoIP).
- **File analysis**: strings, VirusTotal, YARA.
- **Sandboxing**: Joe Sandbox, Cuckoo Sandbox.
- **Pattern recognition**: regular expressions; interpreting suspicious
  commands.
- **Email analysis**: MXToolbox (headers, SPF/DKIM/DMARC records).
- **User and entity behavior analysis (UEBA)**: OpenUBA.
- **File formats**: JSON, XML, YAML, EVTX.
- **Programming / scripting languages**: Python, PowerShell, shell script
  (read and recognise, not write from scratch).

### 1.4 Explain threat intelligence and threat-hunting concepts
- **Threat actors**: advanced persistent threat (APT), insider threat.
- **Tactics, techniques and procedures (TTPs)**: heat maps (coverage against a
  technique matrix), Pyramid of Pain, MITRE ATT&CK, attribution.
- **Confidence-level impacts**: timeliness, relevance, accuracy.
- **Collection methods and sources**: open-source intelligence (OSINT),
  closed-source intelligence, threat-intelligence sharing.
- **Indicators of compromise (IoCs)**: collection, analysis, application /
  usage; types — atomic and behavioral.
- **Threat modeling**: STRIDE.
- **Threat mapping**.
- **Cyber deception** (honeypots, honeytokens and similar decoys).

### 1.5 Explain the importance of efficiency and process improvement in security operations
- **Standardize processes**: manage and facilitate team coordination; create
  playbooks / runbooks.
- **Streamline operations**: automation and orchestration — SOAR,
  infrastructure as code (IaC); data enrichment — rule / alert tuning,
  dashboard creation.
- **Technology and tool integration**: APIs, webhooks, plug-ins.

### 1.6 Summarize concepts related to the use of AI in security operations
- **AI risks**: hallucinations, data exposure, model poisoning, malicious
  prompts.
- **Governance**: legal or regulatory compliance, AI usage policies.
- **Use cases**: comparing artifacts, analyzing log files, document creation,
  incident investigation, event correlation, automation and orchestration.

## 3. Domain 2 — Vulnerability Management (26%)

### 2.1 Given a scenario, implement the appropriate vulnerability scanning method
- **Asset inventory** (you cannot scan what you do not know you own).
- **Planning considerations**: scheduling, operations (effect on the business),
  performance (load on targets and network), sensitivity levels, segmentation
  (scanner placement and reach), regulatory requirements.
- **Scan types**: internal vs. external; agent vs. agentless; credentialed vs.
  non-credentialed; passive vs. active.
- **Discovery**: mapping scans, device fingerprinting.
- **Security baseline scanning** against: PCI DSS, CIS benchmarks, the ISO
  27000 series.

### 2.2 Given a scenario, analyze output from vulnerability assessment tools
- **Network scanning and mapping**: Angry IP Scanner, Masscan.
- **Multipurpose tools**: Nmap, Metasploit Framework (MSF), Maltego, Recon-ng.
- **Web application scanners**: Burp Suite, Zed Attack Proxy (ZAP), Nikto.
- **Vulnerability scanners**: Nessus, Nuclei, OpenVAS.
- **Cloud infrastructure assessment**: ScoutSuite, Prowler, Trivy, Checkov.
- **Breach and attack simulation (BAS)**: Atomic Red Team, Caldera.
- (Acronym list hints at findings a candidate should recognise in output:
  LFI, RFI, SSL.)

### 2.3 Given a scenario, analyze data to prioritize and mitigate vulnerabilities
- **Criteria**: exploitability, active exploitation / threat intelligence,
  asset value, impact, patch / remediation availability, true and false
  positives, true and false negatives.
- **Scoring methods**: CVSS metrics; Exploit Prediction Scoring System (EPSS).
- **Context awareness**: internal, external, isolated.
- **Mitigation strategies**: attack surface management, secure coding best
  practices, patching and configuration management, exceptions, compensating
  controls.
- **Validation of remediation** (rescan / retest).

### 2.4 Explain concepts related to control types, risks, and vulnerability management
- **Control types**: administrative, technical, physical.
- **Control functions**: preventative, detective, responsive, corrective.
- **Risk concepts**: risk appetite, residual risk, inherent risk.
- **Risk management strategies**: accept, transfer, avoid, mitigate.
- **Policies, governance and service-level objectives (SLOs)**.
- **Application security**: static application security testing (SAST),
  dynamic application security testing (DAST), OWASP Software Assurance
  Maturity Model (SAMM).
- **Third-party risk**: supply chain, software composition analysis (SCA),
  software bill of materials (SBOM).

## 4. Domain 3 — Incident Response and Management (24%)

### 3.1 Summarize concepts related to attack methodology frameworks
- Cyber Kill Chain.
- Diamond Model of Intrusion Analysis.
- MITRE ATT&CK.

### 3.2 Summarize the incident response process
- Seven named phases, in this order: preparation, detection, analysis,
  containment, eradication, recovery, post-incident.

### 3.3 Given a scenario, implement incident response techniques
- **Getting ready**: developing plans (incident response plan, communication
  plan); creating playbooks; defining roles; performing training (tabletop,
  simulation).
- **Seeing it**: log collection; log correlation; log augmentation and
  enrichment; alerts and notifications.
- **Sizing it**: triage; establishing a timeline; determining severity and
  impact; prioritization.
- **Evidence gathering**: chain of custody, data integrity validation,
  preservation, legal hold.
- **Acting**: isolating affected targets; escalation; remediation and
  verification; release from isolation; performing restoration.
- **Learning**: root cause analysis (RCA); corrective action development.

## 5. Domain 4 — Reporting and Communication (16%)

### 4.1 Explain the importance of vulnerability management reporting and communication
- Vulnerability scan reports.
- Compliance findings.
- Risk scorecards.
- **Action plans**: escalation, dependencies.
- **Inhibitors to remediation**: contractual agreements, organizational
  governance, business process interruption, degrading functionality, legacy
  systems, proprietary systems, patch availability.
- Stakeholder identification and communication.
- **Metrics and KPIs**: trends, top risks, service-level agreement (SLA).

### 4.2 Explain the importance of security operations and incident response reporting and communication
- Incident declaration and escalation.
- Executive summary.
- **Communication plan**: stakeholder identification, legal team, public
  relations, regulatory reporting agencies, law enforcement, customers.
- **Operational security awareness**: communication channels (assume the usual
  ones may be watched; use out-of-band).
- **Post-incident reporting**: after action report, lessons learned, root cause
  analysis.
- Shift / incident handover.
- **Internal threat intelligence report**: tailored to the organization and
  its environment.
- **Metrics and KPIs**: alert volume, false-positive rate, true-positive rate,
  mean time to close, mean time to detect, mean time to respond, mean time to
  remediate, phishing campaign click rate.

## 6. Other terms from the official acronym list

Not tied to one objective, but fair game: ASN, BC, DR, CASB, CERT, CSIRT, CHD,
DLP, GDB, IDS, IPS, LFI, RFI, MFA, MOU, OSSTMM, OWASP, PII, PKI, SDLC, SDN,
SSO, UTM. (The document expands ASN as "Anonymous System Number", EPSS with
"First Exploitability Prediction..." / "Exploitability Predication..." and
ZTNA as both "Architecture" and "Access"; the usual expansions are Autonomous
System Number, Exploit Prediction Scoring System (published by FIRST) and Zero
Trust Network Access [RECALL].)

Suggested lab software in the document: Windows (Commando VM), Linux (Kali),
an open-source UTM appliance, Metasploitable, a SIEM (Graylog, ELK, Splunk),
tcpdump, Wireshark, OpenVAS, Nessus, and cloud instances (Azure, AWS, GCP).

## 7. What the base course (`cysa_plus.yaml`) covers

The base teaches the core of every objective in 14 units (`cy-1a` … `cy-4c`).
The gaps left for part files are listed at the top of `cysa_plus.yaml` and in
the base author's report; in short: tool-by-tool depth for 1.3 and 2.2,
encryption / data protection and device management in 1.1, the named
baselines in 2.1, SAMM in 2.4, and exam-hard best-answer practice everywhere.
