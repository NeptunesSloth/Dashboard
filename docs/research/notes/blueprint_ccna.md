# Cisco CCNA blueprint (state as of 25 November 2026)

Researcher notes for the `ccna` course. Source-quality legend:
- **[VENDOR]** = read this session on Cisco's own site or in Cisco's official exam-topics PDF.
- **[3P]** = third-party source only; not confirmed on a Cisco page this session.
- **[RECALL]** = written from the researcher's own knowledge; not opened this session.

The topic lists below are **paraphrased** from Cisco's public exam-topics documents. The
numbering (1.1, 1.1.a ...) is Cisco's, so that authors can trace an item to a topic.

## The one thing to know first: the exam changes on 3 February 2027

There are two published blueprints under the same exam number, 200-301:

| | CCNA v1.1 | CCNA v2.0 |
|---|---|---|
| Status today | **Current, live exam** | Announced; not yet testable |
| Dates | Last date to test: 2 February 2027 | First date to test: 3 February 2027 |
| Domains | 6 | 5 |
| Topics document | dated 2024 | dated 2026 |

Both dates are on Cisco's CCNA certification page. [VENDOR]

The `ccna` course now follows **v2.0** (revised November 2026): the header has
the five v2.0 domains (25/25/20/20/10), every unit is tagged to one of them, the
topics v2.0 added are in `ccna_v2.yaml` (units `cn-v2a`..`cn-v2e`), and topics it
dropped sit in background units `cn-bg-1`..`cn-bg-3` under domain `x` with weight
0, so mock exams never draw them. v1.1 stays the live exam until 2 February 2027;
someone sitting it before then should still study the background units. No unit
or item id changed. Sections 1-3 below describe v1.1 and are kept for reference.

## 1. Exam facts (v1.1)

| Fact | Value | Source |
|---|---|---|
| Exam name | CCNA Exam v1.1 (200-301); the associated course is "Implementing and Administering Cisco Solutions (CCNA)" | [VENDOR] topics PDF |
| Exam code | 200-301 (the version, v1.1, is not part of the code) | [VENDOR] topics PDF, exam page |
| Duration | 120 minutes | [VENDOR] topics PDF, exam page |
| Languages | English, Japanese | [VENDOR] exam page |
| Price | US$300, or Cisco Learning Credits | [VENDOR] exam page |
| Prerequisites | None | [VENDOR] certification page |
| Certification validity | Three years; recertify by exam or by 30 Continuing Education credits | [VENDOR] certification page |
| Passing score | **Not published.** Cisco: "Cisco does not publish exam passing scores"; they are set by statistical analysis and are subject to change | [VENDOR] exam policies page |
| Number of questions | **Not published by Cisco.** Prep sites estimate about 100 (figures of 100-120 are quoted) | [3P] unverified |
| Question formats | Cisco's certification page names the formats only for v2.0: "performance-based questions, multiple choice, and drag-and-drop". No Cisco page read this session states the v1.1 formats. Multiple choice (single and multiple answer), drag-and-drop and lab/simulation items are widely reported for v1.1 | v2.0 [VENDOR]; v1.1 [3P]/[RECALL] |
| Navigation | Candidates cannot go back to a previous question | [RECALL] unverified this session |
| Retake policy | Wait 5 calendar days after a failed attempt; after a pass, 180 days before retaking the same exam number | [VENDOR] exam policies page |
| Score report | Given at the end of the exam, with performance broken out by section | [VENDOR] exam policies page |
| Scope note | The topic list is a "general guideline"; related topics may appear and the list may change without notice | [VENDOR] topics PDF |

Domain weights (v1.1), exactly as printed in the topics PDF [VENDOR]:

| # | Domain | Weight |
|---|---|---|
| 1.0 | Network Fundamentals | 20% |
| 2.0 | Network Access | 20% |
| 3.0 | IP Connectivity | 25% |
| 4.0 | IP Services | 10% |
| 5.0 | Security Fundamentals | 15% |
| 6.0 | Automation and Programmability | 10% |

In-app settings chosen for the course (ours, not Cisco's): quick trial 25 questions in
30 minutes, pass mark 85%, full mock 100 questions in 120 minutes. The 85% mark is
deliberately strict because Cisco publishes no pass mark to aim at.

### Sources

- Cisco, "CCNA Exam v1.1 (200-301)" exam topics PDF (4 pages, (c) 2024, Cisco Public):
  https://learningcontent.cisco.com/documents/marketing/exam-topics/200-301-CCNA-v1.1.pdf — read in full. [VENDOR]
- Cisco, "Implementing and Administering Cisco Solutions (200-301 CCNA) v2.0" exam topics PDF
  (3 pages, (c) 2026, Cisco Public):
  https://learningcontent.cisco.com/documents/marketing/exam-topics/200-301_CCNA_v2.0_Exam_Topics_PDF.pdf — read in full. [VENDOR]
- Cisco, 200-301 CCNA exam page (duration, languages, price):
  https://www.cisco.com/site/us/en/learn/training-certifications/exams/ccna.html [VENDOR]
- Cisco, CCNA certification page (version dates, prerequisites, validity, v2.0 formats):
  https://www.cisco.com/site/us/en/learn/training-certifications/certifications/enterprise/ccna/index.html [VENDOR]
- Cisco, certification exam policies (passing scores, retakes, score reports):
  https://www.cisco.com/site/us/en/learn/training-certifications/exams/policies.html [VENDOR]
- Cisco Learning Network topic pages (https://learningnetwork.cisco.com/s/ccna-exam-topics,
  .../s/ccna-v1-1-exam-topics, .../s/ccna-v2-exam-topics) would not render for an automated
  reader this session; the PDFs above carry the same lists.
- Third party, used only for the question-count estimate and the v1.1 start date
  (20 August 2024): https://computingforgeeks.com/ccna-exam-topics/ and
  https://achievable.me/exams/ccna/resources/ccna-exam-topics/ [3P]

### Unverified

- The number of questions (Cisco does not publish it).
- The v1.1 question formats and the no-going-back rule, on a Cisco page.
- The date v1.1 took effect (20 August 2024) — third-party only.

## 2. Exam topics, v1.1 (the syllabus for the `ccna` course)

Verbs matter. "Configure and verify" topics can be tested hands-on; "describe",
"explain", "compare", "interpret" and "recognize" topics are knowledge questions.

### 1.0 Network Fundamentals — 20%

- **1.1** Explain what each network component does and where it fits:
  - 1.1.a routers
  - 1.1.b Layer 2 switches and Layer 3 switches
  - 1.1.c next-generation firewalls and intrusion prevention systems
  - 1.1.d access points
  - 1.1.e controllers
  - 1.1.f endpoints
  - 1.1.g servers
  - 1.1.h Power over Ethernet
- **1.2** Describe the characteristics of network topology architectures:
  - 1.2.a two-tier (collapsed core)
  - 1.2.b three-tier
  - 1.2.c spine-leaf
  - 1.2.d WAN
  - 1.2.e small office / home office
  - 1.2.f on-premises and cloud
- **1.3** Compare physical interfaces and cabling:
  - 1.3.a single-mode fiber, multimode fiber and copper
  - 1.3.b connection types: Ethernet shared media and point-to-point
- **1.4** Identify interface and cable problems: collisions, errors, duplex mismatch, speed mismatch.
- **1.5** Compare TCP with UDP.
- **1.6** Configure and verify IPv4 addressing and subnetting.
- **1.7** Describe private IPv4 addressing.
- **1.8** Configure and verify IPv6 addressing and prefixes.
- **1.9** Describe the IPv6 address types:
  - 1.9.a unicast: global, unique local and link-local
  - 1.9.b anycast
  - 1.9.c multicast
  - 1.9.d modified EUI-64
- **1.10** Verify IP parameters on client operating systems: Windows, macOS and Linux.
- **1.11** Describe wireless principles:
  - 1.11.a non-overlapping Wi-Fi channels
  - 1.11.b SSID
  - 1.11.c radio frequency
  - 1.11.d encryption
- **1.12** Explain virtualization fundamentals: server virtualization, containers and VRFs.
- **1.13** Describe switching concepts:
  - 1.13.a MAC learning and aging
  - 1.13.b frame switching
  - 1.13.c frame flooding
  - 1.13.d the MAC address table

### 2.0 Network Access — 20%

- **2.1** Configure and verify normal-range VLANs that span several switches:
  - 2.1.a access ports, for data and for voice
  - 2.1.b the default VLAN
  - 2.1.c connectivity between VLANs (inter-VLAN routing)
- **2.2** Configure and verify connectivity between switches:
  - 2.2.a trunk ports
  - 2.2.b 802.1Q
  - 2.2.c the native VLAN
- **2.3** Configure and verify the Layer 2 discovery protocols: Cisco Discovery Protocol and LLDP.
- **2.4** Configure and verify EtherChannel with LACP, at Layer 2 and at Layer 3.
- **2.5** Interpret the basic operation of Rapid PVST+ spanning tree:
  - 2.5.a root bridge (primary and secondary), root port and the other port names
  - 2.5.b port states and port roles
  - 2.5.c PortFast
  - 2.5.d root guard, loop guard, BPDU filter and BPDU guard
- **2.6** Describe Cisco wireless architectures and access point modes.
- **2.7** Describe how WLAN components connect physically: AP, WLC, access and trunk ports, and LAG.
- **2.8** Describe the ways of reaching a device for management: Telnet, SSH, HTTP, HTTPS, console, TACACS+/RADIUS, and cloud-managed.
- **2.9** Interpret the wireless LAN controller GUI configuration for client connectivity: creating a WLAN, security settings, QoS profiles and advanced settings.

### 3.0 IP Connectivity — 25%

- **3.1** Interpret the parts of a routing table:
  - 3.1.a routing protocol code
  - 3.1.b prefix
  - 3.1.c network mask
  - 3.1.d next hop
  - 3.1.e administrative distance
  - 3.1.f metric
  - 3.1.g gateway of last resort
- **3.2** Determine how a router makes a forwarding decision by default:
  - 3.2.a longest prefix match
  - 3.2.b administrative distance
  - 3.2.c routing protocol metric
- **3.3** Configure and verify static routing for IPv4 and for IPv6:
  - 3.3.a default route
  - 3.3.b network route
  - 3.3.c host route
  - 3.3.d floating static route
- **3.4** Configure and verify single-area OSPFv2:
  - 3.4.a neighbor adjacencies
  - 3.4.b point-to-point networks
  - 3.4.c broadcast networks (DR/BDR selection)
  - 3.4.d router ID
- **3.5** Describe the purpose, functions and concepts of first hop redundancy protocols.

### 4.0 IP Services — 10%

- **4.1** Configure and verify inside source NAT, using static entries and pools.
- **4.2** Configure and verify NTP in client mode and in server mode.
- **4.3** Explain the role of DHCP and DNS in the network.
- **4.4** Explain what SNMP does in network operations.
- **4.5** Describe syslog features, including facilities and severity levels.
- **4.6** Configure and verify the DHCP client and DHCP relay.
- **4.7** Explain the QoS forwarding per-hop behavior: classification, marking, queuing, congestion, policing and shaping.
- **4.8** Configure network devices for remote access using SSH.
- **4.9** Describe the capabilities and functions of TFTP and FTP in the network.

### 5.0 Security Fundamentals — 15%

- **5.1** Define the key security concepts: threats, vulnerabilities, exploits and mitigation techniques.
- **5.2** Describe the elements of a security program: user awareness, training and physical access control.
- **5.3** Configure and verify device access control using local passwords.
- **5.4** Describe the elements of a password policy: management, complexity, and alternatives to passwords (multifactor authentication, certificates, biometrics).
- **5.5** Describe IPsec remote-access VPNs and site-to-site VPNs.
- **5.6** Configure and verify access control lists.
- **5.7** Configure and verify the Layer 2 security features: DHCP snooping, dynamic ARP inspection and port security.
- **5.8** Compare the concepts of authentication, authorization and accounting.
- **5.9** Describe the wireless security protocols: WPA, WPA2 and WPA3.
- **5.10** Configure and verify a WLAN in the controller GUI using WPA2 PSK.

### 6.0 Automation and Programmability — 10%

- **6.1** Explain how automation affects network management.
- **6.2** Compare traditional networks with controller-based networking.
- **6.3** Describe controller-based, software-defined architecture (overlay, underlay and fabric):
  - 6.3.a separation of the control plane and the data plane
  - 6.3.b northbound and southbound APIs
- **6.4** Explain AI (generative and predictive) and machine learning in network operations. (Added in v1.1.)
- **6.5** Describe the characteristics of REST-based APIs: authentication types, CRUD, HTTP verbs and data encoding.
- **6.6** Recognize the capabilities of configuration management mechanisms such as Ansible and Terraform. (v1.1 replaced the older Puppet/Chef wording.)
- **6.7** Recognize the components of JSON-encoded data.

## 3. What the base course covers, by topic (v1.1)

`sect_academy/packs/ccna.yaml` teaches the core of each domain. Units:

| Unit | Domain | Subject | Topics touched |
|---|---|---|---|
| cn-1a | 1 | Components, architectures, interface faults, switching | 1.1 (part), 1.2.a-c, 1.4, 1.13 |
| cn-1b | 1 | IPv4 addressing, subnetting, TCP and UDP | 1.5, 1.6, 1.7 |
| cn-1c | 1 | IPv6 addressing | 1.8, 1.9 |
| cn-1d | 1 | Wireless principles, virtualization, client checks | 1.10 (part), 1.11.a-c, 1.12 |
| cn-2a | 2 | VLANs, trunks, inter-VLAN routing | 2.1, 2.2 |
| cn-2b | 2 | Spanning tree, EtherChannel, CDP and LLDP | 2.3 (part), 2.4 (Layer 2), 2.5 (part) |
| cn-2c | 2 | Wireless architectures and management access | 2.6, 2.7, 2.8 (part), 2.9 (part) |
| cn-3a | 3 | Reading the routing table | 3.1, 3.2 |
| cn-3b | 3 | Static routes, IPv4 and IPv6 | 3.3 |
| cn-3c | 3 | Single-area OSPFv2: configuration and neighbours | 3.4.a, 3.4.d |
| cn-3d | 3 | OSPF network types, DR/BDR, FHRP | 3.4.b, 3.4.c, 3.5 |
| cn-4a | 4 | NAT, DHCP and DNS | 4.1, 4.3 (part), 4.6 |
| cn-4b | 4 | NTP, SNMP, syslog, SSH, QoS, file transfer | 4.2, 4.4 (part), 4.5 (part), 4.7 (part), 4.8, 4.9 (part) |
| cn-5a | 5 | Security concepts, local passwords, AAA, VPNs | 5.1 (part), 5.3, 5.4 (part), 5.5 (part), 5.8 |
| cn-5b | 5 | Access control lists | 5.6 |
| cn-5c | 5 | Layer 2 security and wireless security | 5.7, 5.9, 5.10 (part) |
| cn-6a | 6 | Controller-based networking and AI | 6.1, 6.2, 6.3, 6.4 |
| cn-6b | 6 | REST APIs, JSON, Ansible and Terraform | 6.5, 6.6, 6.7 |

Not yet covered by the base (work for the part files):

- **Domain 1** — 1.1: endpoints, servers, IPS as a separate item, routers and Layer 2 switches as roles, PoE classes and verification. 1.2: three-tier in detail, WAN (MPLS, Metro Ethernet, internet VPN, SD-WAN), SOHO, on-premises versus cloud. 1.3: all of it (fiber types, copper categories and distances, shared media versus point-to-point). 1.4: CRC, runts, giants and input errors as distinct symptoms. 1.6: VLSM design across several subnets. 1.8: SLAAC and DHCPv6 on clients, verification commands. 1.9.c: IPv6 multicast groups and solicited-node addresses. 1.10: macOS commands; Windows beyond ipconfig. 1.11: SSID/BSS/ESS terms, RF behaviour (absorption, reflection, channel width), 1.11.d encryption. 1.12: hypervisor types compared, virtual switching.
- **Domain 2** — 2.1: the default VLAN and its rules, VLAN creation and naming, the voice VLAN with CDP, Layer 3 switch routing (ip routing, routed ports) in full. 2.2: DTP modes table, 802.1Q tag fields. 2.3: LLDP configuration and verification, CDP/LLDP timers, disabling per interface. 2.4: Layer 3 EtherChannel, load-balancing method, PAgP as a contrast. 2.5: root primary/secondary configuration, designated and backup ports, RSTP states (discarding, learning, forwarding), port costs, loop guard, BPDU filter. 2.6: bridge, mesh, SE-Connect and sniffer modes, embedded and cloud-based controllers. 2.8: console, HTTP/HTTPS and AAA servers for management in detail. 2.9: WLAN advanced settings, interface types on the WLC.
- **Domain 3** — 3.1: every route code (including O IA, O E1/E2, EIGRP D EX), route age, parent and child routes. 3.3: IPv6 floating and host routes, static routes with only an exit interface. 3.4: OSPF states in troubleshooting, MTU and area mismatches, default-information originate, passive-interface default, show ip ospf interface and show ip protocols, loopback behaviour. 3.5: HSRP versions, virtual MAC formats, tracking, verification output.
- **Domain 4** — 4.1: outside local/global, PAT to an interface address, clearing and debugging translations, pool exhaustion. 4.2: NTP authentication, loopback as source, show ntp status, clock and time zone. 4.3: DNS record types and the lookup chain; IOS DHCP server pools. 4.4: SNMP versions, community strings, MIB and OID, get versus set, informs. 4.5: syslog facilities, message format, logging destinations (console, monitor, buffer), timestamps. 4.7: classification methods (NBAR), CoS versus DSCP values, trust boundaries, queuing types (CBWFQ, LLQ), congestion avoidance (WRED). 4.9: copying IOS images and configs, the IOS file system.
- **Domain 5** — 5.1: named attack types (spoofing, DoS, reflection and amplification, man-in-the-middle, reconnaissance, malware classes, social engineering) and their mitigations. 5.2: all of it. 5.3: console and auxiliary line passwords, password types 5, 8 and 9, exec-timeout, login banners. 5.4: password management and complexity, certificates. 5.5: IPsec building blocks (IKE, AH versus ESP, tunnel versus transport), GRE over IPsec, TLS-based client VPNs. 5.6: named ACL configuration and editing by sequence number, ACLs and locally generated traffic, common port matches. 5.7: DHCP snooping rate limits and option 82, DAI validation checks and trusted ports, port-security aging and err-disable recovery. 5.9: enterprise (802.1X/EAP) modes, WPA3 features (PMF, forward secrecy). 5.10: the full GUI workflow.
- **Domain 6** — 6.1: more operational scenarios. 6.2/6.3: Cisco Catalyst Center (DNA Center) features, SD-Access roles (edge, border, control node), SD-WAN components, the management plane. 6.4: machine-learning types, risks and limits of AI output. 6.5: authentication types compared (basic, API key, token, OAuth), URI structure, response codes, XML and YAML as encodings. 6.6: push versus pull, Ansible inventory/module/template terms, Terraform state and providers, how they differ from Puppet and Chef. 6.7: nested objects, data types, spotting invalid JSON in depth.

## 4. Exam topics, v2.0 (from 3 February 2027) — for the course revision

Read from Cisco's v2.0 topics PDF [VENDOR]; paraphrased. The description adds that
candidates "may be required to evaluate output and recommendations from agentic AI and
digital network assistants". Duration stays 120 minutes.

| # | Domain | Weight |
|---|---|---|
| 1.0 | Network Infrastructure and Connectivity | 25% |
| 2.0 | Switching and Network Access | 25% |
| 3.0 | IP Routing | 20% |
| 4.0 | Network Services and Security | 20% |
| 5.0 | AI, and Network Operations and Management | 10% |

### 1.0 Network Infrastructure and Connectivity — 25%
- **1.1** Diagnose interface and cable problems, copper and fiber: collisions, errors, duplex mismatch, speed, distance, interface, signal levels, pin-out and cable type.
- **1.2** Describe the role and function of hypervisors, virtual machines and containers.
- **1.3** Troubleshoot IPv4 address configuration, assignment and subnetting, public and private.
- **1.4** Troubleshoot IPv6 address configuration, assignment and prefix sizing (unicast and modified EUI-64).
- **1.5** Describe wireless principles: 1.5.a band and channel selection; 1.5.b RF characteristics; 1.5.c security protocols; 1.5.d causes of interference.
- **1.6** Troubleshoot wired and wireless client connectivity on Windows, macOS and Linux: IP configuration, reachability and wireless security parameters.
- **1.7** Troubleshoot the DHCPv4 client, server and relay on IOS devices.

### 2.0 Switching and Network Access — 25%
- **2.1** Configure infrastructure connectivity, switch to switch and switch to router: 2.1.a Layer 2 and Layer 3 physical interfaces; 2.1.b Layer 2 802.1Q trunks; 2.1.c Layer 2 and Layer 3 LACP port-channels; 2.1.d switch virtual interfaces.
- **2.2** Configure Layer 2 switch-port attributes for edge hosts (VLAN, PoE, port channel, LACP): 2.2.a desktops, printers and IoT appliances; 2.2.b wireless access points, standalone and controller-based; 2.2.c IP phones; 2.2.d virtualized hosts; 2.2.e network appliances.
- **2.3** Validate network documentation using CDP and LLDP.
- **2.4** Troubleshoot basic Layer 2 and Layer 3 connectivity and device operation using show commands (including logs), ping, extended ping, traceroute and packet-capture output.
- **2.5** Configure Rapid PVST+: 2.5.a root bridge (primary/secondary), root port and other port names; 2.5.b port states and roles; 2.5.c PortFast; 2.5.d root guard, loop guard and BPDU guard.

### 3.0 IP Routing — 20%
- **3.1** Interpret a routing table to find a packet's next hop: routing protocol, prefix and mask, administrative distance, metric, default route.
- **3.2** Troubleshoot IPv4 and IPv6 static routing: 3.2.a default; 3.2.b network; 3.2.c host; 3.2.d floating static.
- **3.3** Configure single-area OSPFv2 for IPv4 and OSPFv3 for IPv6: 3.3.a neighbor adjacencies (authentication excluded); 3.3.b point-to-point; 3.3.c broadcast (DR/BDR selection); 3.3.d router ID.
- **3.4** Interpret the operational status of first hop redundancy protocols (HSRP and VRRP).

### 4.0 Network Services and Security — 20%
- **4.1** Configure devices with local usernames and as an AAA client (TACACS+ and RADIUS) for management.
- **4.2** Manage configuration and software files with secure transfer: SFTP and SCP.
- **4.3** Configure NAT and PAT on IOS XE routers.
- **4.4** Diagnose problems with DNS records (A, AAAA, CNAME, MX, NS, PTR) affecting host, web and mail access by name.
- **4.5** Describe IPsec remote-access and site-to-site VPNs (protocols and transport modes).
- **4.6** Configure IPv4 ACLs: standard, extended, numbered and named.
- **4.7** Configure Layer 2 security: 4.7.a DHCP snooping; 4.7.b dynamic ARP inspection; 4.7.c storm control; 4.7.d RA guard; 4.7.e port security.

### 5.0 AI, and Network Operations and Management — 10%
- **5.1** Describe the role of agentic AI in network operations.
- **5.2** Select a prompt for a generative AI system to support operations, considering data classification, output format, persona and instructions.
- **5.3** Describe network management approaches: device-based, cloud-based, controller-based, automation-based and infrastructure as code.
- **5.4** Describe the function of SNMP in network operations.
- **5.5** Use configuration management mechanisms such as Ansible to execute commands.
- **5.6** Interpret syslog message content, severity levels and facilities.

### What moves between v1.1 and v2.0

- **Gone from the list**: component roles and topology architectures (old 1.1, 1.2), TCP versus UDP, VRFs, switching concepts as a separate topic, wireless architectures and the WLC GUI (old 2.6, 2.7, 2.9, 5.10), NTP, QoS, TFTP/FTP, security-program and password-policy topics, REST APIs, JSON, SDN overlay/underlay, Terraform by name, BPDU filter.
- **New**: OSPFv3, storm control, RA guard, SFTP/SCP, DNS record troubleshooting, the IOS DHCP server, PoE and SVI configuration, extended ping and packet captures, agentic AI and prompt selection, infrastructure as code as a management approach.
- **Verb shift**: many "describe" and "configure and verify" topics become "troubleshoot", "diagnose" or "configure"; Rapid PVST+ moves from "interpret" to "configure".
- Units of the v1.1 course map across roughly as: cn-1b, cn-1c, cn-1d and cn-4a (DHCP) to v2 domain 1; cn-1a (interface faults), cn-2a and cn-2b to domain 2; cn-3a to cn-3d to domain 3; cn-4a (NAT, DNS), cn-5a, cn-5b and cn-5c to domain 4; cn-4b (SNMP, syslog), cn-6a and cn-6b (Ansible) to domain 5.
