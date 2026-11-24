# Entry-level cyber-security certification blueprints (state as of 24 November 2026)

Researcher notes. Source-quality legend used throughout:
- **[VENDOR]** = read this session on the vendor's own page or official objectives PDF.
- **[3P]** = third-party source only; not confirmed on a vendor page this session.
- **[RECALL]** = stable textbook/standards fact written from the researcher's own knowledge, with a pointer to the authoritative standard, but the pointer was NOT opened this session. Spot-check before shipping.

Three things changed in 2025-2026 that invalidate most older study material:
1. **Security+ SY0-801 (V8) launched 17 Nov 2026**; SY0-701 is now the "retiring version" (English retires 11 Jun 2027). Domain weights and objective numbering changed.
2. **ISC2 CC has a new outline effective 1 Sep 2026** (new domain names and weights), is now **CAT with 100-125 items**, and the **free-exam program closed to new enrolments on 20 May 2026** (exam is US$199).
3. **NIST SP 800-61 Rev. 3 (April 2025)** superseded Rev. 2, so the classic "four-phase NIST incident response lifecycle" is now the superseded model.

---

## 1. CompTIA Security+ — exam code, versions, dates, format, objectives

### Takeaway
There are two live Security+ exams right now: the new SY0-801 (V8, launched 17 Nov 2026, English only, CompTIA's "recommended version") and SY0-701 (V7, English retires 11 Jun 2027). Format is unchanged (max 90 questions, 90 minutes, MCQ + PBQ, pass 750 on 100-900) but weights shifted toward concepts/threats and away from governance, and V8 adds an AI-threats objective. A question bank must be tagged per version.

### Cited Findings

**Version status and dates**
- CompTIA's Security+ landing page labels V8 "(New Version)" and "the recommended version", and V7 "(Retiring Version)", which "remains available until retirement, with the English exam retiring June 11, 2027, and translated exams retiring August 13, 2027." [VENDOR] — [CompTIA Security+](https://www.comptia.org/en-us/certifications/security/)
- V8: exam code SY0-801, launch date November 17, 2026, retirement "Estimated 3 years after launch", English only, ISO 17024 accredited via ANAB. [VENDOR] — [CompTIA Security+ V8](https://www.comptia.org/en-us/certifications/security/v8/)
- V7: exam code SY0-701, launched November 7, 2023; retires June 11, 2027 (English) and August 13, 2027 (Japanese, Portuguese, Spanish, Thai). [VENDOR] — [CompTIA Security+ V7](https://www.comptia.org/en-us/certifications/security/v7/)
- A Security+ certification earned on SY0-701 does not expire when the exam version retires; it stays valid three years from the test date. [3P] — [Training Camp](https://trainingcamp.com/articles/take-security-701-now-before-the-801-update-hits/)

**Format (identical for both versions)**
- Maximum of 90 questions; multiple-choice and performance-based; 90 minutes; passing score 750 on a scale of 100-900. [VENDOR] — [SY0-801 Exam Objectives v2.0 PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928); [CompTIA Security+ V7](https://www.comptia.org/en-us/certifications/security/v7/)
- Recommended experience, V8: "Security administrator with two years of hands-on experience." V7: CompTIA Network+ plus two years in a security/systems administrator role. Recommendations, not prerequisites. [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928); [CompTIA Security+ V7](https://www.comptia.org/en-us/certifications/security/v7/)
- 750 is a scaled score, not a percentage (it is not "83%"). [3P] — [Destination Certification](https://destcert.com/resources/security-plus-passing-score-2/)

**Domain weights, old vs new**

| Domain | SY0-701 (V7) | SY0-801 (V8) |
|---|---|---|
| 1.0 General Security Concepts | 12% | 16% |
| 2.0 Threats, Vulnerabilities, and Mitigations (V7) / **and Attacks** (V8) | 22% | 24% |
| 3.0 Security Architecture | 18% | 19% |
| 4.0 Security Operations | 28% | 27% |
| 5.0 Security Program Management and Oversight | 20% | 14% |

Sources [VENDOR]: [V7 page](https://www.comptia.org/en-us/certifications/security/v7/); [SY0-801 Objectives PDF v2.0](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)

**SY0-801 (V8) objectives — exact titles and listed topics, from the official "Exam Objectives Document Version 2.0"** (27 objectives: 3/6/4/8/6) [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)

*1.0 General Security Concepts (16%)*
- **1.1 Explain security concepts and controls.** Defense in depth (CIA; AAA; non-repudiation; Zero Trust principles; least privilege). Control categories: technical/logical, managerial/administrative, physical/environmental, operational. Control types: preventive, deterring, corrective, detective, compensating, directive.
- **1.2 Given a scenario, demonstrate the impact of change management processes on security.** CAB/approval, ownership, stakeholders, impact analysis, test results, backout planning, fail forward, maintenance window, SOPs; technical implications (allow/deny lists, restricted activities, downtime, service/application restart, legacy applications, dependencies); documentation; version control.
- **1.3 Explain the importance of using appropriate cryptographic solutions.** PKI (public key, private key, key escrow); certificates (CAs, CRLs, OCSP, self-signed, third-party, root of trust, CSR generation, wildcard); encryption (protocols, symmetric, asymmetric, level: full disk/partition/file/volume/database/record, transport, key exchange, algorithms, key length); digital signatures; salting; tools; obfuscation; hashing algorithms.

*2.0 Threats, Vulnerabilities, and Attacks (24%)*
- **2.1 Explain characteristics of threats and vulnerabilities.** Threat feeds, likelihood, impact, intelligence sources, life cycle; CVSS scoring, prioritization, vulnerability types, CVE.
- **2.2 Describe common threat actors and motivations.** Actors: crime syndicate/organized crime, terrorist, unskilled attacker, hacktivist, insider, accidental/unintentional, competitor, state-sponsored. Motivations: financial, influence, intellectual property, notoriety, espionage, fear/chaos, extortion, general curiosity, revenge, ideological, political, ethical. Attributes: internal/external, resources/funding, sophistication.
- **2.3 Describe threat vectors and sources.** APT; message-based (email, SMS, RCS, IM, collaboration tools); image-based (QR codes, embedded content, CAPTCHA); attachment-based (macros, RTF, PDF); browser-based (extensions, JavaScript, password managers, cookies, session tokens); network-based; remote access (remote desktop, VNC, VPN); endpoint-based (incl. living-off-the-land tools); supply chain (third-party providers, MSPs, logistics, SaaS providers); external media (malicious USB); human-based (impersonation, contractor, visitor, biometric, watering hole); IoT; OT; physical; signal-based (Bluetooth, RF, NFC).
- **2.4 Explain types of vulnerabilities and attack surfaces.** Unsupported/unpatched/obsolete/unmanaged systems; ports and services; applications (race conditions TOC/TOU, malicious update); code (hardcoded secrets, unsafe exception handling); OS-based; virtualization; zero-day; cryptographic; unmanaged/stale credentials; rogue devices; shadow IT; wireless; LLMs; identity providers; mobile; misconfiguration; public repositories; public object storage.
- **2.5 Given a scenario, analyze indicators of malicious activity.** Malware (ransomware, trojan, worm, spyware, adware, virus, rootkit, keylogger); physical (tailgating, shoulder surfing, skimming, forced entry); network (DDoS, protocol downgrade, rogue, sniffing, spoofing, on-path, DNS attacks, cache poisoning); social engineering (smishing, vishing, phishing, whaling, spear phishing, quishing, impersonation, deepfake); application (injection, buffer overflow, replay, privilege escalation, forgery, directory traversal); credential (password spraying, brute force, user enumeration, replay, MFA bypass); IoCs (hash, IP, domain, malicious processes, file system artifacts, excessive resource consumption, plaintext strings, account lockout, impossible travel, concurrent sessions).
- **2.6 Summarize threats and vulnerabilities associated with artificial intelligence (AI) usage.** Model manipulation, poisoning, prompt injection, data loss, bias, explainability, hallucinations, jailbreaking, evasion, privacy, ethical considerations, session hijacking, code execution. *(New in V8.)*

*3.0 Security Architecture (19%)*
- **3.1 Compare and contrast security implications of different architecture models.** Cloud (serverless, multicloud, hybrid/private/public/community), IaC, OT, on-premises, air-gapped, microservices, logical/physical segmentation; technical considerations (availability, resilience, usability, responsibility, compute, power, ease of recovery); business considerations (data sovereignty, classification, cost, ownership, scalability, risk).
- **3.2 Given a scenario, manage the security architecture to best protect the infrastructure.** Device placement, security zones, attack surface, diversity; Zero Trust architecture (user authentication, device health/inventory, application access control); secure communication/access (VPN, remote access, tunneling, least privilege, E2E encrypted messaging, out-of-band management, file transfer, SSE); identity management (gMSAs, least-privilege accounts, privilege creep); failure modes.
- **3.3 Summarize concepts and strategies used to protect data.** Structured/unstructured; states (at rest, in use, in transit); classifications (sensitive, secret, critical, confidential, public, top secret, restricted); methods (masking, hashing, filtering, tokenization, encryption, deidentification, obfuscation); roles (owner, custodian, steward, operator, controller, subprocessor); handling (labeling, geofencing, location); life cycle (creation, management, distribution, retention, disposal); compliance data types.
- **3.4 Explain the importance of resilience and recovery in security architecture.** Hot/cold/warm sites; platform diversity; redundancy (load balancing, clustering, autoscaling, HA, multicloud, UPS/RPS/generator/surge protector); backups (retention, immutability, scope, restoration testing); testing (failover, simulation, parallel processing); DR; BC; capacity planning; recovery metrics RTO, RPO, MTTR, MTBF.

*4.0 Security Operations (27%)*
- **4.1 Given a scenario, apply mitigating controls, techniques, and solutions to secure the environment.** Segmentation, access controls, hardening, sandboxing; deception (honeypot, honeynet, honeyfile, honeytoken, canary account); MDM; application allow/block lists; NIDS/NIPS, HIDS/HIPS, WIPS; firewalls (rate limiting, WAF, rule-based, UTM, layer 4/7); content filter/DLP; endpoint (EDR, XDR, antivirus); NAC (captive portal, 802.1X, posture); secrets scanning; application security (input validation, secure cookies, static analysis, code signing); email security (DMARC, SPF, DKIM, BIMI); OS security (Group Policy, SELinux).
- **4.2 Explain the security implications of proper hardware, software, and data asset management.** Life cycle: planning/scoping, acquisition/procurement, assignment/accounting, monitoring/tracking, disposal/decommissioning.
- **4.3 Given a scenario, perform tasks associated with vulnerability management.** Identification (scanning, IPAM, CSPM, source code review); prioritization (severity, pen-test report review); remediation; verification; reporting (internal; external: bounty program, responsible disclosure).
- **4.4 Explain security alerting and monitoring concepts and tools.** Log aggregation, alerting, scanning, archiving, reporting, alert tuning; benchmarks, agents/agentless, SIEM, antivirus, DLP, vulnerability scanners, packet analyzer; NetFlow, SNMP, syslog, SCAP; port mirroring; dashboards.
- **4.5 Given a scenario, apply concepts related to identity and access management.** Provisioning/deprovisioning, identity proofing, federation, SSO (SAML, LDAP, OAuth); account types (user, privileged, service, third-party, emergency access); MFA (hard token, soft token, biometrics, OTP, backup code); access control models (rule-based, role-based, time-based, mandatory, discretionary, just-in-time); access review; passkey, password managers, passwordless, password best practices.
- **4.6 Given a scenario, apply automation and orchestration solutions to secure operations.** Use cases (user/resource provisioning, desired state, anomaly detection, ticketing); considerations (guardrails, complexity, cost, process risk); AI capabilities (agentic, chatbot, predictive analysis, AI-augmented baselines); CI/CD; workflows.
- **4.7 Summarize concepts associated with incident response activities.** Preparation (training, testing, tabletop, playbooks, simulation, roles); Identification (detection, advisories, threat hunting); Investigation (digital forensics, chain of custody, e-discovery, preservation); Containment (quarantine/isolation); Negotiation; Eradication/recovery; Notification/external reporting (stakeholders, customers, law enforcement, mandatory); Post-incident (lessons learned, root cause analysis, PIR).
- **4.8 Given a scenario, use data, artifacts and sources to support a security investigation.** Log types; data sources (vulnerability scans, NetFlow/IPFIX, surveillance footage, dashboards, packet captures); file/log integrity; system image (memory dump, bit-level copy, snapshot); stakeholders (HR, legal); log parsing.

*5.0 Security Program Management and Oversight (14%)*
- **5.1 Explain the importance of governance, risk, and compliance artifacts.** Guidelines, standards, procedures (SOP, runbooks), plans (BC, DR), policies (BYOD, AUP, clean desk, IR, data classification/retention, access control, disposal, vulnerability disclosure, privacy).
- **5.2 Explain the impact of risk management processes on the security of the organization.** Identification, assessment, analysis (impact, likelihood, qualitative vs quantitative), risk register, treatment (transfer, accept, avoid, mitigate), BIA, risk appetite, residual risk, SLE, ALE, ARO.
- **5.3 Explain the assessment and management processes associated with third-party risk.** Vendor selection (RFP, RFI, RFQ, EOI, due diligence, conflict of interest); agreements (SLA, SLO, MOU, MOA, NDA, MSA, SOW); monitoring (right to audit, attestation, pen testing); constraints (jurisdiction, ROI, vendor lock-in); rules of engagement.
- **5.4 Summarize elements of effective security compliance.** Compliance training/monitoring (attestations, acknowledgements); consequences (reputational, financial, legal, contractual, sanctions, loss of license); privacy (right to be forgotten, opt-in/opt-out, controller vs processor); legal hold, retention.
- **5.5 Explain concepts associated with audit and assessment activities.** Data gathering (sampling, interviews); reference sources (MITRE ATT&CK, Cyber Kill Chain, Diamond Model); scoping (audit charter); engagement types (gap analysis, internal, external, benchmarking); penetration testing (known/unknown/partially known environment; physical, offensive, defensive, integrated; passive/active reconnaissance).
- **5.6 Given a scenario, apply security awareness concepts to improve organizational security.** Training types, delivery (LMS), effectiveness metrics, topics (social engineering, credential management, remote work, BYOD, BEC, removable media, operational security).

The SY0-801 objectives PDF also carries an official acronym list of roughly 105-110 entries (AAA ... XDR) and a hardware/software lab list (Kali Linux, packet capture, SIEM, vulnerability scanner, etc.). [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)

**SY0-701 (V7) sub-objective topics** (28 objectives: 4/5/4/9/6), as summarised on CompTIA's V7 page [VENDOR] — [CompTIA Security+ V7](https://www.comptia.org/en-us/certifications/security/v7/)
- Domain 1 (12%): security controls (technical, managerial, operational, physical; preventive, deterrent, detective, corrective, compensating, directive); fundamental concepts (CIA, non-repudiation, AAA, zero trust, deception/disruption technology); change management; cryptographic solutions (PKI, encryption, obfuscation, hashing, digital signatures, blockchain).
- Domain 2 (22%): threat actors and motivations; threat vectors and attack surfaces; vulnerabilities; malicious activity indicators; mitigation techniques.
- Domain 3 (18%): architecture models; enterprise infrastructure; data protection; resilience and recovery.
- Domain 4 (28%): computing-resource security techniques; asset management; vulnerability management; alerting and monitoring; enterprise security capabilities (firewall, IDS/IPS, DNS filtering, DLP, NAC, EDR/XDR); IAM; automation and orchestration; incident response; data sources for investigations.
- Domain 5 (20%): governance; risk management; third-party risk; compliance; audits and assessments; security awareness.

**What changed V7 -> V8**
- V7 1.1 + 1.2 merged into V8 1.1; V7 2.5 (mitigations) + 4.1 + 4.5 consolidated into V8 4.1; V7 4.7 automation became V8 4.6; V7 2.1-2.3 restructured into V8 2.1-2.4; new V8 2.6 on AI; 28 objectives became 27. [3P, consistent with the vendor PDF] — [Decryption Digest, 14 Nov 2026](https://www.decryptiondigest.com/blog/comptia-security-plus-sy0-801-vs-sy0-701-what-changed)
- Dion Training (1 Oct 2026) advises not abandoning SY0-701 study mid-way; the deciding factor is whether you can sit it before retirement; new starters with a later test date should target SY0-801. [3P] — [Dion Training](https://www.diontraining.com/blogs/news/comptia-security-sy0-801-what-we-know-about-the-new-exam)

**Price**
- CompTIA raised exam prices on 1 June 2026, taking the US Security+ voucher from $425 to $439. [3P] — [Training Camp](https://trainingcamp.com/articles/how-to-save-money-on-comptia-exam-vouchers-a-practical-guide/); [HackerDNA](https://hackerdna.com/blog/cout-certification-security-plus)
- A failed attempt requires buying another voucher (no discounted retake). [VENDOR] — [CompTIA blog](https://www.comptia.org/en-us/blog/how-much-does-the-comptia-security-certification-cost/)

**Renewal (Continuing Education)**
- Certifications are valid three years; Security+ needs 50 CEUs per three-year cycle; CE fee for Security+ is $150 per three-year period, payable any time in the cycle. [VENDOR] — [CompTIA CEUs](https://www.comptia.org/en-us/resources/ce/learn/earn-continuing-education-units-ceus/); [CompTIA CE renewal fees](https://www.comptia.org/en-us/resources/ce/learn/continuing-education-renewal-fees/)
- Single-activity renewal options (passing the latest exam release, earning a higher-level cert, completing CertMaster CE) renew without CE fees; CertMaster CE for Security+ requires a cert earned on SY0-701 or earlier (i.e. not available for the current exam version). [VENDOR] — [CompTIA CertMaster CE](https://www.comptia.org/en-us/resources/ce/choose/renew-with-a-single-activity/complete-a-comptia-certmaster-ce-course/)
- At least 50% of a training activity's content must map to the exam objectives of the cert being renewed; a 30-day grace period after expiry covers fee payment/CEU submission only. [VENDOR] — [CompTIA Help Center](https://help.comptia.org/hc/en-us/articles/14382051258004-What-Are-the-Fees-to-Renew-My-Certification)

### Inferences
- The app should treat SY0-801 as the default track and keep SY0-701 as a time-boxed legacy track that auto-expires on 11 Jun 2027. About 80-90% of concept flashcards are shared; the differences are tagging, weights, the AI objective (2.6), and the incident-response step list.
- Mock exams: 90 items / 90 minutes, weighted 16/24/19/27/14 (V8) => roughly 14 / 22 / 17 / 24 / 13 questions. Include a few PBQ-style items (drag-and-drop matching, firewall-rule ordering, log analysis).
- V8 shifted many verbs to "Given a scenario, apply/perform/manage" (4.1, 4.3, 4.5, 4.6, 4.8, 3.2, 5.6), so question banks should lean scenario-based rather than definition recall.
- The official acronym list (~107 entries) is a ready-made, copyright-safe flashcard seed (terms are facts; write original definitions).

### Gaps
- **Security+ price not confirmed on CompTIA's own store page** (the vendor pages fetched show no price). $439 is third-party-reported; whether SY0-801 vouchers are priced differently is unknown.
- CompTIA's exact count of PBQs per exam is not published; third-party reports of "3-5 PBQs" were not verified.
- The V7 numbered objective titles (1.1-5.6) were taken from the CompTIA page summary, not the SY0-701 PDF. From recall the V7 numbering is 1.1 controls, 1.2 fundamental concepts, 1.3 change management, 1.4 cryptography; 2.1 actors, 2.2 vectors, 2.3 vulnerabilities, 2.4 indicators, 2.5 mitigations; 3.1-3.4; 4.1 computing resources, 4.2 asset management, 4.3 vulnerability management, 4.4 alerting/monitoring, 4.5 enterprise capabilities, 4.6 IAM, 4.7 automation, 4.8 incident response, 4.9 data sources; 5.1-5.6. [RECALL — verify against the SY0-701 PDF].
- Whether SY0-801 translated versions are scheduled is unknown (English only at launch).

---

## 2. CompTIA Network+ — N10-009

### Takeaway
N10-009 (V9, launched 20 Jun 2024) is still the only current Network+ exam; CompTIA shows no successor on the product page and estimates retirement in 2027. Max 90 questions, 90 minutes, pass 720 on 100-900, five domains with troubleshooting (24%) and concepts (23%) dominant.

### Cited Findings
- Exam code N10-009, version V9, launched June 20, 2024; retirement "usually three years after launch (estimated 2027)"; no V10/N10-010 mentioned. [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/)
- Maximum of 90 questions; multiple-choice and performance-based; 90 minutes; passing score 720 on a scale of 100-900; languages English, German, Japanese, Portuguese, Spanish. [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/)
- Recommended experience: CompTIA A+ plus 9-12 months hands-on in a junior network administrator/network support technician role. [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/)
- Domain weights: 1.0 Networking Concepts 23%; 2.0 Network Implementation 20%; 3.0 Network Operations 19%; 4.0 Network Security 14%; 5.0 Network Troubleshooting 24%. [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/)
- The exam has 25 objectives across the five domains. [3P] — [Decryption Digest](https://www.decryptiondigest.com/blog/comptia-network-plus-n10-009-exam-objectives-explained)
- Sub-objective topics as listed on the CompTIA page [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/):
  - **1.0 Networking Concepts:** OSI model layers; networking appliances (router, switch, firewall, IDS/IPS, load balancer, proxy, NAS, SAN, wireless); cloud concepts (NFV, VPC, network security groups, cloud gateways, public/private/hybrid, SaaS/IaaS/PaaS); ports and protocols (FTP, SFTP, SSH, Telnet, SMTP, DNS, DHCP, HTTP, HTTPS, SNMP, LDAP, RDP, SIP); traffic types (unicast, multicast, anycast, broadcast); transmission media (802.11, cellular, satellite; fiber, coaxial, DAC); transceivers/connectors (SC, LC, ST, MPO, RJ11, RJ45, F-type, BNC); topologies (mesh, hybrid, star/hub-and-spoke, spine-and-leaf, point-to-point, three-tier, collapsed core); IPv4 addressing (public/private, APIPA, RFC 1918, loopback, VLSM, CIDR, classes A-E).
  - **2.0 Network Implementation:** routing (static, dynamic: BGP, EIGRP, OSPF; route selection; NAT, PAT, FHRP, VIP, subinterfaces); switching (VLANs, interface configuration, spanning tree, MTU, jumbo frames); wireless (channels, frequencies, SSID, network types, encryption, guest networks, authentication, antennas, APs); physical installations (power, environmental).
  - **3.0 Network Operations:** documentation (physical/logical diagrams, rack diagrams, cable maps, asset inventory, IPAM, SLA, wireless survey); life-cycle (EOL, EOS, decommissioning); change and configuration management; monitoring (SNMP, flow data, packet capture, baselines, log aggregation, API integration, port mirroring); disaster recovery (RPO, RTO, MTTR, MTBF; cold/warm/hot sites; active-active/active-passive; testing); network services (DHCP, SLAAC, DNS, NTP, PTP, NTS); access and management (VPN, SSH, GUI, API, console).
  - **4.0 Network Security:** logical security (encryption in transit/at rest, PKI, IAM, MFA, SSO, RADIUS, LDAP, SAML, TACACS+, time-based authentication, least privilege, RBAC, geofencing); physical security; deception (honeypot, honeynet); terminology (risk, vulnerability, exploit, threat, CIA); audits/compliance (data locality, PCI DSS, GDPR); segmentation (IoT, IIoT, SCADA, ICS, OT, guest, BYOD); attacks (DoS/DDoS, VLAN hopping, MAC flooding, ARP poisoning/spoofing, DNS poisoning/spoofing, rogue devices, evil twin, on-path, social engineering); defenses (hardening, NAC, key management, ACLs, URL/content filtering, zones, screened subnet).
  - **5.0 Network Troubleshooting:** methodology; cabling and physical interface issues (counters, port status, PoE, transceiver mismatch, signal strength); network service issues (STP, VLAN assignment, ACLs, routing tables, default routes, address pool exhaustion, wrong gateway/IP/mask); performance issues (congestion, latency, packet loss, wireless interference); tools and protocols (protocol analyzer, command-line tools, cable testers, Wi-Fi analyzer).
- Renewal: Network+ needs 30 CEUs per three-year cycle; CE fee $150 per three-year period. [VENDOR] — [CompTIA CEUs](https://www.comptia.org/en-us/resources/ce/learn/earn-continuing-education-units-ceus/); [CompTIA CE renewal fees](https://www.comptia.org/en-us/resources/ce/learn/continuing-education-renewal-fees/)
- Price: one third-party table shows Network+ moving from $390 to $399, but that page's dates are internally inconsistent. [3P, weak] — [Crucial Exams](https://crucialexams.com/posts/blog/comptia-voucher-price-increase-2026); StationX still lists $390 — [StationX](https://app.stationx.net/vouchers/comptia-network-plus-voucher)

### Inferences
- Mock exam: 90 items / 90 minutes weighted 23/20/19/14/24 => about 21 / 18 / 17 / 13 / 21 questions.
- Because N10-009 is roughly 2.5 years into a ~3-year life and CompTIA estimates 2027 retirement, the app should store the exam code as data (not hard-code it) and expect an N10-010 announcement during 2027.
- Troubleshooting (24%) is the largest domain and is scenario/PBQ-heavy: build "symptom -> most likely cause -> next step" items, not just definitions.

### Gaps
- **Numbered objective titles were not read from the N10-009 PDF this session.** From recall the numbering is: 1.1 OSI; 1.2 appliances/applications/functions; 1.3 cloud; 1.4 ports, protocols, services, traffic types; 1.5 transmission media and transceivers; 1.6 topologies/architectures; 1.7 IPv4 addressing; 1.8 evolving use cases (SDN/SD-WAN, VXLAN, zero trust, SASE/SSE, IaC, IPv6); 2.1 routing; 2.2 switching; 2.3 wireless; 2.4 physical installation; 3.1 organizational processes (documentation, life cycle, change/config management); 3.2 monitoring; 3.3 DR; 3.4 IPv4/IPv6 network services; 3.5 access and management; 4.1 basic security concepts; 4.2 attack types; 4.3 apply security features; 5.1 methodology; 5.2 cabling/physical; 5.3 network services; 5.4 performance; 5.5 tools/protocols. [RECALL — verify against the official PDF; the CompTIA page summary above omits objective 1.8's "evolving use cases" topics.]
- Network+ price not confirmed on a vendor page; treat "~$390-399" as approximate.
- No vendor statement found on an N10-010 date.

---

## 3. ISC2 Certified in Cybersecurity (CC)

### Takeaway
The CC changed substantially in 2026: a new exam outline took effect 1 September 2026 (five domains, renamed and re-weighted, with cloud, zero trust, IAM lifecycle, threat intel, security testing and AI-adjacent topics added), the exam is CAT with 100-125 items in 2 hours, and the free-exam "One Million Certified in Cybersecurity" program stopped taking new participants on 20 May 2026. Any material describing "100 questions, 5 domains at 26/10/22/24/18, free exam" is out of date.

### Cited Findings
- Outline "EFFECTIVE DATE: SEPTEMBER 1, 2026"; length 2 hours; 100-125 items; "Multiple choice and advanced item types"; "The CC exam uses Computerized Adaptive Testing (CAT) for all exams."; passing grade 700 out of 1000; languages English, Chinese, Japanese, German, Spanish. [VENDOR] — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline)
- Domain weights (2026 outline) [VENDOR] — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline):

| # | 2026 domain | Weight | 2025 domain it replaces | Old weight |
|---|---|---|---|---|
| 1 | Security Principles | 24% | Security Principles | 26% |
| 2 | Security Governance | 17.3% | Business Continuity, Disaster Recovery & Incident Response Concepts | 10% |
| 3 | Identity and Access Management (IAM) Concepts | 20% | Access Controls Concepts | 22% |
| 4 | Networking and Cloud Security Concepts | 21.3% | Network Security | 24% |
| 5 | Security Operations and Incident Response | 17.3% | Security Operations | 18% |

  Old-vs-new mapping and old weights: [VENDOR] — [ISC2 Insights, Aug 2026](https://www.isc2.org/insights/2026/08/inside-the-updated-isc2-cc-exam)
- Sub-objectives (2026 outline) [VENDOR] — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline):
  - **1.1** Understand cybersecurity concepts (confidentiality, integrity, availability, AAA, non-repudiation, privacy). **1.2** Understand risk management concepts (lifecycle, processes). **1.3** Understand governance concepts (regulations and laws; frameworks and guidelines; policies, standards e.g. ISO, CIS; procedures). **1.4** Understand cybersecurity controls (technical, administrative, physical). **1.5** Maintain professional and ethical conduct (professional code of conduct; due care and due diligence; ISC2 Code of Ethics).
  - **2.1** Plan Governance, Risk, and Compliance (purpose, importance, frameworks and tools). **2.2** Understand redundancy (Business Continuity, Disaster Recovery). **2.3** Understand security awareness (organizational culture; concepts e.g. social engineering, password protection, phishing). **2.4** Measure cybersecurity effectiveness (key metrics, KRIs; dashboards, scorecards, reports).
  - **3.1** Understand identity life cycle management (role definition, provision, review, deprovision, frameworks and tools). **3.2** Understand logical access controls (least privilege, separation of duties, access control models).
  - **4.1** Understand network security (OSI, TCP/IP, IPv4, IPv6, VPN; firewalls: ports, applications; wireless: Wi-Fi, Bluetooth; embedded systems, ICS, IoT). **4.2** Understand network security architecture (segmentation: firewall zones, VLAN, micro-segmentation; defense in depth; zero trust). **4.3** Understand cloud security (five characteristics: broad network access, rapid elasticity, measured service, on-demand self-service, resource pooling; service models; deployment models; shared security model).
  - **5.1** Understand data security (handling: classification, labeling, masking, sanitization; encryption: symmetric, asymmetric, hashing, quantum-resistant cryptography). **5.2** Understand security operations (logging and monitoring; event triage; threat actors; cyber threat intelligence; threat frameworks). **5.3** Understand Incident Response (IR plan; IR exercises e.g. testing, tabletop). **5.4** Understand asset protection (asset lifecycle incl. EOL; configuration and change management). **5.5** Understand security testing (blue/purple/red teaming; vulnerability scanning, static analysis, dynamic analysis, threat modeling; physical penetration testing e.g. phishing, tailgating, impersonation).
- The Sept 2026 outline is "the first major content update to the certification" since its August 2022 launch, reflects the latest Job Task Analysis, and integrates foundational AI topics throughout rather than as a separate domain. [VENDOR] — [ISC2 Insights, Aug 2026](https://www.isc2.org/insights/2026/08/inside-the-updated-isc2-cc-exam)
- No work experience is required; the exam must be scheduled and taken within 365 days of purchase. [VENDOR] — [ISC2 CC](https://www.isc2.org/certifications/cc)
- Free-exam program: "ISC2 has closed new enrollments in the program" (One Million Certified in Cybersecurity), effective 20 May 2026; unexpired exam codes "must be used to schedule and take an exam by December 31, 2026"; expired codes cannot be reactivated. [VENDOR] — [ISC2 1MCC](https://www.isc2.org/1MCC)
- "The CC exam fee is U.S. $199." Passing candidates pay a "U.S. $50 Annual Maintenance Fee (AMF)". [VENDOR] — [ISC2 1MCC](https://www.isc2.org/1MCC)

### Inferences
- Mock exam design for CC: fixed-form mocks cannot reproduce CAT, but a 100-item / 120-minute mock weighted 24 / 17 / 20 / 21 / 17 is the closest practical approximation; an optional adaptive mode (difficulty steps up/down per answer, ends between 100 and 125 items) would mirror the real experience. In CAT you cannot go back to earlier items, so the mock should disable back-navigation.
- The published weights sum to 99.9% (24 + 17.3 + 20 + 21.3 + 17.3), which suggests the weights are item-count fractions of a 75-item scored pool (18/13/15/16/13); this is an inference, not an ISC2 statement.
- Old CC question banks under-cover: cloud (service/deployment models, shared responsibility), zero trust, identity lifecycle, GRC metrics/KRIs, threat intelligence and threat frameworks, red/blue/purple teams, static/dynamic analysis, threat modeling, quantum-resistant crypto. BC/DR shrank from its own domain to one sub-objective (2.2).
- The free-exam route is effectively dead for new learners after 31 Dec 2026; the app should present CC as a US$199 exam plus US$50/yr.

### Gaps
- The exact date CC moved from linear to CAT is not stated on the pages read (the outline only says CAT is used "for all exams").
- CC continuing-education requirement not confirmed this session. [RECALL: 45 CPE credits per three-year cycle — verify on isc2.org.]
- Whether ISC2 still offers the CC self-paced course free, or any regional/partner free-voucher schemes, is unconfirmed; the 1MCC page says only that exams and education are "available for purchase".
- How many of the 100-125 items are unscored pretest items is not published on the pages read.

---

## 4. Highest-yield foundational concepts (flashcard seeds)

### Takeaway
The three exams share a large common core (CIA/AAA, control categories and types, crypto basics, PKI, IAM, network fundamentals, risk formulas, BC/DR metrics, incident response). Lists below are deliberately worded as original one-line definitions keyed to the official objectives; version-sensitive items (control-type names, IR step lists) are flagged because CompTIA's wording changed in SY0-801 and NIST's changed in 2025.

### Cited Findings

**Sourcing note:** the *topics* below all appear in the vendor objectives cited in sections 1-3. The *one-line definitions, port numbers and formulas* are [RECALL] — standard facts checked against the researcher's knowledge of the named standards (IANA port registry, RFC 1918, NIST SP 800-30 Rev. 1, NIST SP 800-61, NIST glossary), which were not individually re-opened this session, except where a vendor citation is shown. Authoritative references for spot-checking: [IANA Service Name and Port Number Registry](https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml); [NIST CSRC Glossary](https://csrc.nist.gov/glossary); [NIST SP 800-30 Rev. 1](https://csrc.nist.gov/pubs/sp/800/30/r1/final); [RFC 1918](https://www.rfc-editor.org/rfc/rfc1918).

**Version-sensitive facts (verified this session)**
- SY0-801 control categories: technical/logical, managerial/administrative, physical/environmental, operational. Control types: preventive, deterring, corrective, detective, compensating, directive. (SY0-701 uses "deterrent".) — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928); [V7 page](https://www.comptia.org/en-us/certifications/security/v7/)
- ISC2 CC uses three control categories only: technical, administrative, physical. — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline)
- SY0-801 incident response activities as listed in objective 4.7: Preparation, Identification, Investigation, Containment, Negotiation, Eradication/recovery, Notification/external reporting, Post-incident (lessons learned, root cause analysis, PIR). — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)
- NIST SP 800-61 Rev. 3, "Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile", was published April 2025 (final 3 Apr 2025) and supersedes Rev. 2 (Aug 2012). — [NIST SP 800-61r3](https://csrc.nist.gov/pubs/sp/800/61/r3/final)
- SY0-801 recovery metrics listed: RTO, RPO, MTTR (mean time to repair), MTBF. Risk terms listed: SLE, ALE, ARO, risk appetite, residual risk, BIA; treatments: transfer, accept, avoid, mitigate. — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)
- Network+ N10-009 listed protocols: FTP, SFTP, SSH, Telnet, SMTP, DNS, DHCP, HTTP, HTTPS, SNMP, LDAP, RDP, SIP; DR metrics RPO, RTO, MTTR, MTBF. — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/)

#### 4A. Security+ core (55 cards) [RECALL definitions]
1. **Confidentiality** — only authorized parties can read data (encryption, access control).
2. **Integrity** — data is not altered without authorization and alteration is detectable (hashing, signatures).
3. **Availability** — systems and data are usable when needed (redundancy, backups, DDoS protection).
4. **AAA** — Authentication (prove identity), Authorization (what you may do), Accounting (log what you did).
5. **Non-repudiation** — a party cannot credibly deny an action; provided by digital signatures plus logging.
6. **Defense in depth** — multiple layered, independent controls so one failure is not a breach.
7. **Least privilege** — grant only the minimum access needed for the job.
8. **Zero Trust** — never trust by network location; verify user, device and context on every request.
9. **Control categories** — technical, managerial, operational, physical (who/what implements the control).
10. **Control types** — preventive (stop), detective (find), corrective (fix), deterrent (discourage), compensating (alternative), directive (instruct).
11. **Symmetric encryption** — one shared key for encrypt and decrypt; fast; key distribution is the problem (AES).
12. **Asymmetric encryption** — public/private key pair; slow; solves key exchange and enables signatures (RSA, ECC).
13. **Hashing** — one-way fixed-length digest for integrity; not encryption (SHA-256; MD5 and SHA-1 are broken for collision resistance).
14. **Salting** — random value added to each password before hashing to defeat rainbow tables.
15. **Digital signature** — hash of the message encrypted with the sender's private key; verified with the public key; gives integrity, authentication, non-repudiation.
16. **Encrypt-to-recipient rule** — encrypt with the recipient's public key; recipient decrypts with their private key.
17. **PKI** — CAs, certificates and keys that bind a public key to an identity.
18. **CSR** — request containing a public key and identity sent to a CA to be signed.
19. **CRL vs OCSP** — CRL is a published list of revoked certificates; OCSP is a real-time status query for one certificate.
20. **Wildcard certificate** — one certificate covering all first-level subdomains of a domain (*.example.com).
21. **Key escrow** — a trusted third party holds a copy of keys for recovery.
22. **Data states** — at rest (stored), in transit (on the network), in use (in memory/being processed).
23. **Tokenization vs masking** — tokenization swaps data for a meaningless token mapped in a vault; masking hides part of the value (e.g. ****1234).
24. **Threat / vulnerability / risk** — threat = potential cause of harm; vulnerability = weakness; risk = likelihood x impact of a threat exploiting a vulnerability.
25. **CVE vs CVSS** — CVE is an identifier for a specific known vulnerability; CVSS is a 0-10 severity score.
26. **Zero-day** — vulnerability exploited before a patch is available.
27. **Phishing family** — phishing (email), spear phishing (targeted), whaling (executives), vishing (voice), smishing (SMS), quishing (QR code).
28. **BEC** — attacker impersonates or compromises a business email account to induce payment or data transfer.
29. **Malware types** — virus (needs a host and user action), worm (self-propagates), trojan (disguised), ransomware (encrypts for payment), rootkit (hides with high privilege), keylogger, spyware.
30. **On-path attack** — attacker secretly relays/alters traffic between two parties (formerly "man-in-the-middle").
31. **DoS vs DDoS** — exhausting a resource from one source vs many distributed sources.
32. **Injection (SQLi)** — untrusted input interpreted as code/query; mitigated by input validation and parameterized queries.
33. **XSS vs CSRF** — XSS runs attacker script in the victim's browser; CSRF tricks the victim's authenticated browser into sending a request.
34. **Buffer overflow** — writing past a memory buffer to crash or hijack execution.
35. **Password spraying vs brute force** — a few common passwords against many accounts vs many guesses against one account.
36. **Privilege escalation** — gaining higher rights than granted (vertical) or another user's rights (horizontal).
37. **Race condition (TOC/TOU)** — state changes between the time something is checked and the time it is used.
38. **Prompt injection** — crafted input that makes an AI model ignore its instructions (SY0-801 obj. 2.6).
39. **Data poisoning** — corrupting training data to manipulate model behaviour (SY0-801 obj. 2.6).
40. **MFA factors** — something you know, have, are (plus somewhere you are / something you do); two of the same type is not MFA.
41. **SSO / federation** — one login for many systems / trust of identities across organizations (SAML, OAuth, OIDC).
42. **SAML vs OAuth** — SAML exchanges authentication assertions (XML); OAuth delegates authorization (tokens).
43. **Access control models** — DAC (owner decides), MAC (labels/clearance), RBAC (role-based), rule-based, ABAC (attributes), just-in-time.
44. **IDS vs IPS** — IDS detects and alerts (out of band); IPS sits inline and blocks.
45. **WAF** — layer-7 firewall filtering HTTP(S) application attacks.
46. **SIEM** — aggregates and correlates logs to alert on security events.
47. **EDR / XDR** — endpoint detection and response / the same extended across network, cloud and identity.
48. **DLP** — detects and blocks unauthorized movement of sensitive data.
49. **SPF / DKIM / DMARC** — authorized sending IPs / cryptographic signature of mail / policy and reporting that ties the two to the visible From domain.
50. **SLE = AV x EF** — single loss expectancy = asset value x exposure factor.
51. **ALE = SLE x ARO** — annualized loss expectancy = single loss x expected occurrences per year.
52. **Risk treatments** — avoid, transfer (insurance/outsourcing), mitigate, accept; what remains is residual risk.
53. **RTO vs RPO** — RTO = maximum tolerable time to restore service; RPO = maximum tolerable data loss measured in time.
54. **MTBF vs MTTR** — average time between failures vs average time to repair.
55. **Hot / warm / cold site** — fully equipped and near-real-time / partially equipped / space and power only.
56. **Incident response (SY0-701 wording)** — Preparation, Detection, Analysis, Containment, Eradication, Recovery, Lessons learned. *(SY0-801 wording differs — see version-sensitive facts above.)*
57. **Chain of custody** — documented, unbroken record of who handled evidence and when.
58. **Order of volatility** — collect most volatile evidence first: CPU cache/registers, RAM, swap, disk, remote logs, backups.
59. **Pen test environments** — known (white box), partially known (gray), unknown (black).
60. **Agreement types** — SLA (service levels), MOU (intent, usually non-binding), MOA, NDA (confidentiality), MSA (master terms), SOW (specific work).

#### 4B. Network+ core (50 cards) [RECALL definitions]
1. **OSI layers (7 to 1)** — Application, Presentation, Session, Transport, Network, Data Link, Physical.
2. **OSI PDUs** — Transport = segment (TCP) / datagram (UDP); Network = packet; Data Link = frame; Physical = bits.
3. **Devices by layer** — hub/repeater L1; switch/bridge L2; router L3; multilayer switch L2-3; L7 firewall/proxy/load balancer up to L7.
4. **TCP vs UDP** — TCP is connection-oriented and reliable (handshake, ACKs); UDP is connectionless and best-effort.
5. **TCP three-way handshake** — SYN, SYN-ACK, ACK.
6. **FTP** — TCP 20 (data), 21 (control).
7. **SSH / SFTP** — TCP 22.
8. **Telnet** — TCP 23 (cleartext; replace with SSH).
9. **SMTP** — TCP 25; mail submission with TLS (SMTPS) on 587.
10. **DNS** — UDP/TCP 53 (TCP for zone transfers and large responses).
11. **DHCP** — UDP 67 (server), 68 (client).
12. **TFTP** — UDP 69.
13. **HTTP / HTTPS** — TCP 80 / TCP 443.
14. **NTP** — UDP 123.
15. **SNMP** — UDP 161 (queries), 162 (traps); v3 adds authentication and encryption.
16. **LDAP / LDAPS** — TCP 389 / TCP 636.
17. **SMB** — TCP 445.
18. **Syslog** — UDP 514.
19. **SQL Server** — TCP 1433.
20. **RDP** — TCP 3389.
21. **SIP** — 5060 (unencrypted), 5061 (TLS).
22. **POP3 / IMAP** — 110 / 143; secure versions 995 / 993.
23. **RADIUS vs TACACS+** — RADIUS: UDP 1812/1813, combines authn+authz, encrypts only the password; TACACS+: TCP 49, separates AAA, encrypts the whole payload.
24. **DHCP DORA** — Discover, Offer, Request, Acknowledge.
25. **DNS records** — A (IPv4), AAAA (IPv6), CNAME (alias), MX (mail), NS (name server), PTR (reverse), TXT (text, e.g. SPF), SOA (zone authority).
26. **RFC 1918 private ranges** — 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16.
27. **APIPA** — 169.254.0.0/16 self-assigned when DHCP fails.
28. **Loopback** — 127.0.0.0/8 (commonly 127.0.0.1); IPv6 ::1.
29. **CIDR host formula** — usable hosts = 2^(host bits) - 2; /24 = 254, /26 = 62, /30 = 2.
30. **Subnet mask equivalents** — /24 = 255.255.255.0, /25 = .128, /26 = .192, /27 = .224, /28 = .240, /30 = .252.
31. **IPv6 basics** — 128-bit; link-local fe80::/10; global unicast 2000::/3; no broadcast (uses multicast); SLAAC self-configures addresses.
32. **Traffic types** — unicast (one-to-one), broadcast (one-to-all), multicast (one-to-group), anycast (one-to-nearest).
33. **NAT vs PAT** — NAT translates addresses; PAT maps many private addresses to one public address using port numbers.
34. **VLAN / 802.1Q** — logical L2 segmentation; 802.1Q tags frames on trunk links.
35. **STP** — Spanning Tree Protocol blocks redundant links to prevent L2 loops.
36. **Routing protocol types** — OSPF = link-state IGP; EIGRP = advanced distance-vector IGP; BGP = path-vector EGP used between autonomous systems.
37. **Default gateway** — the router a host sends traffic to for destinations outside its own subnet.
38. **FHRP / VIP** — first-hop redundancy (e.g. VRRP, HSRP) presents a shared virtual IP so the gateway survives a router failure.
39. **MTU / jumbo frames** — standard Ethernet MTU is 1500 bytes; jumbo frames are larger (commonly ~9000).
40. **Wi-Fi standards** — 802.11a 5 GHz; b 2.4; g 2.4; n (Wi-Fi 4) 2.4/5; ac (Wi-Fi 5) 5 GHz; ax (Wi-Fi 6/6E) 2.4/5/6 GHz.
41. **2.4 GHz non-overlapping channels** — 1, 6, 11.
42. **WPA2 vs WPA3** — WPA2 uses AES-CCMP with PSK or 802.1X; WPA3 replaces PSK with SAE.
43. **802.1X** — port-based network access control using an authentication server (typically RADIUS).
44. **PoE standards** — 802.3af 15.4 W; 802.3at (PoE+) 30 W; 802.3bt (PoE++) up to 60/90-100 W.
45. **Copper cable limits** — twisted pair max 100 m; Cat 5e 1 Gbps; Cat 6 10 Gbps to 55 m; Cat 6a 10 Gbps to 100 m.
46. **Fiber** — single-mode = long distance, laser; multimode = shorter distance, LED/VCSEL; connectors LC, SC, ST, MPO.
47. **Topologies** — star/hub-and-spoke, mesh, spine-and-leaf (data center, every leaf connects to every spine), three-tier (core/distribution/access), collapsed core (core+distribution merged).
48. **Cloud service models** — IaaS (you manage OS up), PaaS (you manage apps/data), SaaS (you manage data/users).
49. **Troubleshooting methodology (7 steps, in order)** — 1 identify the problem; 2 establish a theory of probable cause; 3 test the theory; 4 establish a plan of action; 5 implement the solution or escalate; 6 verify full functionality and implement preventive measures; 7 document findings, actions, outcomes and lessons learned.
50. **Common attacks** — ARP poisoning (falsified ARP replies redirect LAN traffic), MAC flooding (overflow the switch CAM table), VLAN hopping (reach another VLAN via trunk abuse/double tagging), evil twin (rogue AP imitating a legitimate SSID), DNS poisoning (false DNS answers).
51. **CLI tools** — ping (reachability, ICMP), traceroute/tracert (path), nslookup/dig (DNS), ipconfig/ip (addressing), arp (ARP cache), netstat (connections), nmap (port scan), tcpdump (capture).
52. **Screened subnet** — a buffer network (formerly "DMZ") exposing public services between untrusted and internal zones.

#### 4C. ISC2 CC core (45 cards; many overlap with 4A) [RECALL definitions unless cited]
1. **CIA triad** — confidentiality, integrity, availability.
2. **AAA** — authentication, authorization, accounting (added to CC domain 1 in the 2026 outline). — [ISC2 Insights](https://www.isc2.org/insights/2026/08/inside-the-updated-isc2-cc-exam)
3. **Non-repudiation** — inability to deny having performed an action.
4. **Privacy** — an individual's right to control how their personal information is collected, used and shared.
5. **Authentication factors** — know / have / are; MFA requires two or more different types.
6. **Risk terms** — asset, threat, vulnerability, likelihood, impact.
7. **Risk treatment** — avoid, accept, mitigate (reduce), transfer.
8. **Risk appetite/tolerance** — amount of risk an organization is willing to accept.
9. **Risk management lifecycle** — identify, assess/analyze, treat, monitor.
10. **Control categories (ISC2)** — technical, administrative, physical. — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline)
11. **Governance hierarchy** — laws/regulations -> policies (management intent, mandatory) -> standards (mandatory specifics) -> procedures (step-by-step) ; guidelines are recommended, not mandatory.
12. **Due care vs due diligence** — due care = acting as a reasonable person would to protect; due diligence = the ongoing investigation/verification that supports it.
13. **ISC2 Code of Ethics canons (in order)** — (1) protect society, the common good, necessary public trust and confidence, and the infrastructure; (2) act honorably, honestly, justly, responsibly, and legally; (3) provide diligent and competent service to principals; (4) advance and protect the profession.
14. **GRC** — governance (direction), risk management, compliance (meeting obligations).
15. **KRI vs KPI** — key risk indicator signals rising risk exposure; KPI measures performance against goals.
16. **Business continuity** — keeping critical business functions running during a disruption.
17. **Disaster recovery** — restoring IT systems and data after a disruption.
18. **BIA** — business impact analysis identifies critical functions and the impact of losing them (drives RTO/RPO).
19. **RTO / RPO** — maximum time to restore / maximum acceptable data loss in time.
20. **Security awareness** — training that changes behaviour (phishing, password hygiene, social engineering).
21. **Social engineering** — manipulating people rather than systems (phishing, pretexting, tailgating).
22. **Identity lifecycle** — define roles, provision, review, deprovision. — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline)
23. **Least privilege** — minimum access necessary.
24. **Separation of duties** — no single person can complete a sensitive process alone.
25. **Access control models** — DAC (owner discretion), MAC (system-enforced labels), RBAC (roles), ABAC (attributes).
26. **Privileged access management** — tighter control and monitoring of administrator-level accounts.
27. **OSI vs TCP/IP** — OSI has 7 layers; TCP/IP has 4 (link/network access, internet, transport, application).
28. **IPv4 vs IPv6** — 32-bit dotted decimal vs 128-bit hexadecimal.
29. **Common ports** — 22 SSH, 25 SMTP, 53 DNS, 80 HTTP, 443 HTTPS, 3389 RDP.
30. **Firewall** — filters traffic between zones by rule (ports/addresses; next-gen firewalls also by application).
31. **VPN** — encrypted tunnel across an untrusted network.
32. **Segmentation** — VLANs, firewall zones, micro-segmentation limit lateral movement.
33. **Defense in depth** — layered controls.
34. **Zero trust** — no implicit trust based on network location; continuous verification.
35. **IoT / ICS risks** — weak defaults, hard to patch, long-lived; isolate on separate segments.
36. **Cloud characteristics (NIST five)** — on-demand self-service, broad network access, resource pooling, rapid elasticity, measured service. — [ISC2 CC Exam Outline](https://www.isc2.org/certifications/cc/cc-certification-exam-outline)
37. **Cloud service models** — SaaS, PaaS, IaaS.
38. **Cloud deployment models** — public, private, hybrid, community.
39. **Shared responsibility model** — provider secures the cloud itself; customer secures what they put in it; the split shifts by service model; the customer is always responsible for their data.
40. **Data handling** — classification, labeling, masking, retention, sanitization/destruction.
41. **Symmetric / asymmetric / hashing** — one shared key / key pair / one-way digest for integrity.
42. **Quantum-resistant (post-quantum) cryptography** — algorithms designed to resist attacks by quantum computers, which threaten RSA/ECC.
43. **Logging and monitoring** — collecting events to detect and investigate; SIEM correlates them.
44. **Event vs incident** — event = any observable occurrence; incident = an event that harms or threatens CIA.
45. **Incident response plan and exercises** — documented roles and steps; tested via tabletop and simulation.
46. **Threat actors** — nation-state, organized crime, hacktivist, insider, unskilled attacker; differ by motivation and capability.
47. **Threat frameworks** — MITRE ATT&CK (tactics/techniques), Cyber Kill Chain (attack stages).
48. **Red / blue / purple team** — attackers / defenders / the two working together.
49. **SAST vs DAST** — static analysis inspects source code without running it; dynamic analysis tests the running application.
50. **Configuration and change management** — baselines plus controlled, approved, documented, reversible changes.
51. **Asset lifecycle / EOL** — end-of-life products stop receiving patches and must be replaced or isolated.

### Inferences
- A shared "core" deck of ~60 cards (CIA/AAA, controls, crypto, IAM, risk, BC/DR, network basics, cloud models) can be tagged to all three exams, with exam-specific overlays. This matches the overlap visible in the three official outlines.
- Control terminology must be exam-aware: CompTIA tests four categories + six types; ISC2 CC tests three categories (technical/administrative/physical). A question that is correct for one exam can be wrong for the other.
- Incident-response ordering questions are the highest-risk item for staleness: SY0-701 wording, SY0-801 wording, and NIST 800-61 Rev. 2 vs Rev. 3 all differ. Each question should cite which model it is testing.

### Gaps
- The flashcard definitions and port numbers were not individually re-verified against sources this session (see sourcing note); they are standard, but a reviewer should spot-check ports against IANA and formulas against a current official study guide before shipping.
- NIST SP 800-61 Rev. 3's internal structure was not read this session. [RECALL: Rev. 2's lifecycle was Preparation -> Detection & Analysis -> Containment, Eradication & Recovery -> Post-Incident Activity; Rev. 3 instead organizes recommendations under the six CSF 2.0 functions Govern, Identify, Protect, Detect, Respond, Recover — verify.]
- NIST SP 800-30 definitions were not opened; the SLE/ALE/ARO formulas are CompTIA study-canon rather than NIST 800-30 text.
- SY0-701's exact IR step wording (card 4A-56) and the 7-step Network+ troubleshooting wording (4B-49) are from recall of the official PDFs.

---

## 5. How to study — evidence and experienced-candidate consensus

### Takeaway
Reliable published evidence here is thin and mostly vendor-blog opinion: the common advice is to book the exam once practice scores on unseen questions are consistently in the 80-85% range, to treat practice exams as diagnostics (review every miss and every lucky guess), and to practise PBQ formats and skip-and-return timing. No vendor publishes a readiness threshold.

### Cited Findings
- One exam-tips site recommends scoring 85%+ consistently, "at least 5 consecutive practice tests at this level", before scheduling Security+. [3P, single source] — [PrepForCerts](https://prepforcerts.org/comptia-security-plus-exam-tips)
- An instructor quoted by Infosec Institute uses a lower bar: 75% on an official practice test made of questions you have never seen. [3P] — [Infosec Institute](https://www.infosecinstitute.com/resources/professional-development/certification-test-anxiety/)
- The pass mark is a scaled score (750 on 100-900), not a percentage, so practice-test percentages do not map directly to it. [3P] — [Destination Certification](https://destcert.com/resources/security-plus-passing-score-2/)
- Practice exams are most useful as diagnostics: the valuable output is the set of missed questions plus those answered correctly without knowing why; take a cold baseline exam first to find weak domains. [3P] — [DEV Community](https://dev.to/tiltedlunar123/practice-exams-are-a-diagnostic-not-a-scoreboard-how-to-study-for-security-sy0-701-1gib)
- PBQs appear at the start of the exam; common advice is to flag time-consuming PBQs, do the multiple-choice items, and return. [3P] — [Infosec Institute](https://www.infosecinstitute.com/resources/securityplus/security-exam-information-performance-based-questions/)
- PBQs are reported to award partial credit (e.g. per correct firewall rule). [3P, unverified by CompTIA] — [DEV Community](https://dev.to/tiltedlunar123/stop-letting-pbqs-eat-the-first-15-minutes-of-your-security-exam-25a8)
- CompTIA says its exams combine multiple-choice, drag-and-drop and performance-based items. [VENDOR] — [CompTIA blog](https://www.comptia.org/en-us/blog/what-is-on-the-comptia-network-exam/)
- CompTIA explicitly tells candidates to "review the complete list and attain a working knowledge of all listed acronyms"; the SY0-801 list is ~107 acronyms. [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)
- CompTIA notes the bulleted examples in the objectives "are not exhaustive lists" and other related examples may appear on the exam. [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)
- A third-party SY0-801 comparison cites Dunlosky et al. (2013) as support for practice testing and distributed practice as study techniques. [3P citing academic work; the paper itself was not opened] — [Decryption Digest](https://www.decryptiondigest.com/blog/comptia-security-plus-sy0-801-vs-sy0-701-what-changed)

### Inferences
- A defensible in-app readiness rule: "ready" when the learner scores >= 80-85% on at least 3 consecutive full-length mocks drawn from **unseen** questions, with no domain below ~70-75%. This is a synthesis of community heuristics, not a vendor or empirically validated threshold — label it as a heuristic in the UI.
- The bank must be large enough that mocks stay "unseen": with a 90-question mock and 3-5 mocks plus domain drills, a minimum of roughly 500-800 original questions per exam is implied; fewer leads to memorised-answer inflation of scores.
- Features that follow from the consensus: per-domain score breakdown, a "missed + guessed" review queue (ask for confidence on each answer), spaced-repetition acronym deck, PBQ-style interactive items (matching, ordering, rule tables, log reading) with partial-credit scoring, and a timer that encourages flag-and-return.
- For the CC (CAT), no back-navigation and variable length mean time-per-item pacing practice (about 58-72 seconds per item for 100-125 items in 120 minutes) matters more than flag-and-return.

### Gaps
- No Professor Messer or Jason Dion primary-source statement of a specific readiness percentage was retrieved this session; the widely repeated "80-85% on Dion/Messer practice exams" community heuristic is unverified here.
- No peer-reviewed or vendor-published data linking practice-score thresholds to pass rates was found. CompTIA and ISC2 do not publish pass rates on the pages read.
- No reliable figure for typical study hours or total practice-question volume was found.
- Number of PBQs per exam and their scoring weight are not published by CompTIA.

---

## 6. Copyright and exam-security rules (brain dumps)

### Takeaway
CompTIA's own objectives document states that using unauthorized "brain dump" material leads to certification revocation and suspension from testing under the Candidate Agreement. The app must therefore use only original questions written against the public objectives, never recalled or scraped live exam items — and should not copy CompTIA's objectives PDF wholesale either.

### Cited Findings
- "CompTIA Certifications, LLC is not affiliated with and does not authorize, endorse, or condone utilizing any content provided by unauthorized third-party training sites (aka 'brain dumps'). Individuals who utilize such materials in preparation for any CompTIA examination will have their certifications revoked and be suspended from future testing in accordance with the CompTIA Candidate Agreement." Questions about whether material is unauthorized go to examsecurity@comptia.org. [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)
- CompTIA states candidates who memorize brain-dump content face a ban from CompTIA exams of at least 12 months, loss of certification, and score invalidation; ignorance that material was unauthorized is not a defence. [VENDOR] — [CompTIA: Understanding Exam Fraud](https://www.comptia.org/en-us/blog/understanding-exam-fraud/); [CompTIA: Why Brain Dumps Don't Work](https://www.comptia.org/en/blog/why-brain-dumps-dont-work/)
- CompTIA uses data forensics to identify candidates with prior knowledge of exam content and may refer severe cases to third-party agencies. [VENDOR] — [CompTIA data forensics policy](https://www.comptia.org/en-us/resources/test-policies/comptia-data-forensics/)
- Educators who distribute or endorse exam dumps face disciplinary action including revocation and suspension or permanent ban. [VENDOR] — [CompTIA educator policy](https://www.comptia.org/en/resources/test-policies/educator-policy/)
- The objectives PDF itself carries: "Reproduction or dissemination prohibited without the written consent of CompTIA, Inc." [VENDOR] — [SY0-801 Objectives PDF](https://lecbyo.files.cmp.optimizely.com/download/77f3bd3223ac11f180820e495f189928)

### Inferences
- Safe pattern for the app: (a) store objective *numbers* and short paraphrased topic labels as tags, linking out to the vendor's page for the official text; (b) generate/write all questions and explanations originally; (c) never ingest user-submitted "questions I saw on the exam"; (d) add a prompt/guardrail so the LLM tutor refuses requests to reproduce real exam items; (e) avoid CompTIA/ISC2 logos and any "official"/"actual exam questions" wording, and include a "not affiliated with or endorsed by CompTIA or ISC2" notice.
- These notes quote objective titles for internal design use; the shipped app should paraphrase rather than reproduce the objectives document.

### Gaps
- The full text of the CompTIA Candidate Agreement was not opened; the statements above are CompTIA's own summaries of it.
- ISC2's exam non-disclosure terms were not retrieved this session. [RECALL: ISC2 candidates accept an NDA prohibiting disclosure of exam content, and violating it breaches the Code of Ethics — verify on isc2.org.]
- This is not legal advice; trademark-usage rules for the names "Security+", "Network+" and "CC" were not researched.

---

## 7. Other entry certifications and a sensible beginner order

### Takeaway
Nothing in this section was verified against vendor pages in this session (the tool budget went to the three primary exams, which had all changed). Treat the content below as orientation from prior knowledge and re-verify before building tracks for these certs.

### Cited Findings
- CompTIA positions A+ as the recommended precursor to Network+ ("CompTIA A+ certification, plus 9 to 12 months of hands-on experience"), and (for V7) Network+ as the recommended precursor to Security+. [VENDOR] — [CompTIA Network+](https://www.comptia.org/en-us/certifications/network/); [CompTIA Security+ V7](https://www.comptia.org/en-us/certifications/security/v7/)
- Earning a higher-level CompTIA certification is one of the fee-free ways to renew a lower one, which makes the A+ -> Network+ -> Security+ -> CySA+ stack self-renewing. [VENDOR] — [CompTIA CertMaster CE / single-activity renewal](https://www.comptia.org/en-us/resources/ce/choose/renew-with-a-single-activity/complete-a-comptia-certmaster-ce-course/)
- ISC2 CC requires no work experience and is positioned as entry-level. [VENDOR] — [ISC2 CC](https://www.isc2.org/certifications/cc)

### Inferences
- **Suggested order for a true beginner:** (0) optional IT basics — A+ or the Google Cybersecurity Certificate if the learner has no IT background; (1) ISC2 CC as a low-cost, concept-only on-ramp (now US$199, so its "free first cert" advantage is gone for new learners — some will reasonably skip it); (2) Network+ (or at least its content: OSI, ports, subnetting) because Security+ assumes it; (3) Security+ SY0-801 — the key employer-recognised baseline; (4) then branch: CySA+ (blue team/SOC analyst), eJPT (hands-on offensive), or SSCP (ISC2 practitioner track, requires experience).
- Because the CC now costs money and its new outline overlaps Security+ domains 1 and 5 heavily, the app could present CC content as the "foundations" tier of a Security+ path rather than as a separate mandatory stop.
- For the app's "basics" bank, priority order is Security+ (801) > Network+ > CC; A+ and the others are lower priority.

### Gaps (all [RECALL], unverified this session — check vendor pages)
- **CompTIA A+**: two exams (Core 1 + Core 2); the 220-1201/220-1202 series is believed to have launched in 2025 with the 220-1101/1102 series retired in late 2025. Dates, weights and price not verified.
- **Google Cybersecurity Certificate** (Coursera): a multi-course, no-exam-centre professional certificate aimed at complete beginners; believed to include a discount on the Security+ voucher. Current course count, price and whether the discount applies to SY0-801 not verified.
- **CompTIA CySA+**: CS0-003 was the current code as of the researcher's knowledge (launched 2023), so a CS0-004 refresh would be due around 2026; whether one has been announced or released was not checked. Recommended after Security+; counts for renewing Security+.
- **eJPT** (INE Security): practical, lab-based junior penetration tester exam (open-book, multi-hour hands-on); current version, price and format not verified.
- **SSCP** (ISC2): practitioner-level; believed to require one year of paid experience in one or more of its domains (or become an Associate of ISC2); outline version, CAT status and price not verified.
- No evidence was gathered this session on employer demand or job-posting frequency for any of these certifications.
