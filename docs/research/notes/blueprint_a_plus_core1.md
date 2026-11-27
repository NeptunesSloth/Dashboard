# CompTIA A+ Core 1 (220-1201, V15) — exam blueprint (state as of 25 November 2026)

Researcher notes for the `a-plus-core1` course. This is the syllabus for the
base course (`sect_academy/packs/a_plus_core1.yaml`) and for every part file
that extends it. Source-quality legend, as in `cert_blueprints.md`:

- **[VENDOR]** = read this session on CompTIA's own page or official objectives PDF.
- **[3P]** = third-party source only.
- **[RECALL]** = textbook fact from the researcher's own knowledge, not opened this session.

The objective and topic lists below are **paraphrased and regrouped** from the
official objectives document; they are complete (every objective, every listed
topic) but are not a copy of it. CompTIA states that its bulleted examples are
not exhaustive: other technologies related to an objective may appear on the exam.

---

## 1. Exam facts

| Fact | Value | Source |
|---|---|---|
| Certification | CompTIA A+ (two exams: Core 1 and Core 2, both from the same series) | [VENDOR] objectives PDF |
| Exam code | **220-1201** (series "V15"; Core 2 is 220-1202) | [VENDOR] PDF + page |
| Launch date | 25 March 2025 | [VENDOR] page |
| Retirement | "Usually three years after launch (estimated 2028)" — no fixed date published | [VENDOR] page |
| Number of questions | Maximum of 90 | [VENDOR] PDF + page |
| Question types | Multiple-choice (single and multiple response), drag-and-drop, performance-based | [VENDOR] page (PDF says "multiple-choice and performance-based") |
| Length | 90 minutes | [VENDOR] PDF + page |
| Passing score | 675 on a scale of 100-900 (scaled score, not a percentage) | [VENDOR] PDF + page |
| Recommended experience | 12 months hands-on in an IT support specialist role (a recommendation, not a prerequisite) | [VENDOR] PDF + page |
| Languages | English, German, Japanese | [VENDOR] page |
| Accreditation | ANAB, ISO 17024 | [VENDOR] PDF |

**Domain weights** [VENDOR, PDF and page agree]:

| Domain | Weight | Objectives |
|---|---|---|
| 1.0 Mobile Devices | 13% | 1.1-1.3 |
| 2.0 Networking | 23% | 2.1-2.8 |
| 3.0 Hardware | 25% | 3.1-3.8 |
| 4.0 Virtualization and Cloud Computing | 11% | 4.1-4.2 |
| 5.0 Hardware and Network Troubleshooting | 28% | 5.1-5.6 |

27 objectives in total (3 / 8 / 8 / 2 / 6).

**Sources**

- Official objectives: "CompTIA A+ Certification Exam Objectives, Exam Number: Core 1 (220-1201) V15, Exam Objectives Document Version 4.0" — <https://lecbyo.files.cmp.optimizely.com/download/34be017cb73211ef8985a6f347fbf652> (CompTIA's document host; downloaded and read in full this session). [VENDOR]
- CompTIA exam page: <https://www.comptia.org/en-us/certifications/a/core-1-v15/> [VENDOR]
- CompTIA's 1101-to-1201 comparison sheet: <https://lecbyo.files.cmp.optimizely.com/download/618cd912a39611efadacb6f62670d066> (weights 15/20/25/11/29 in 220-1101 became 13/23/25/11/28). [VENDOR]
- An earlier **draft** objectives PDF (v1.2) is also in circulation; it was not used.

**Unverified / caveats**

- No exact retirement date exists yet; "estimated 2028" is CompTIA's wording.
- The per-domain question counts are not published; only the percentages are.
- Everything in the "study pointers" lines below is [RECALL] textbook knowledge added by the researcher to help authors; it is not in the objectives document.

### What changed from 220-1101 (for anyone holding older material)

- **The six-step troubleshooting methodology is no longer a tested objective.** The V15 document prints it as a "competency standard" and says explicitly that it will not be tested. Domain 5 is still scenario troubleshooting. The steps, for teaching: identify the problem; establish a theory of probable cause (question the obvious; research if needed); test the theory; establish a plan of action and implement the solution; verify full system functionality and apply preventive measures; document findings, actions and outcomes.
- Networking grew (20% to 23%); Mobile Devices shrank (15% to 13%); troubleshooting 29% to 28%.
- New or newly explicit in V15: 6GHz band, Mini-LED, eSIM, DKIM/SPF/DMARC as TXT-record spam management, ONT, network tap, HSM, direct-burial cable, secured prints / badging / audit logs on printers, ingress/egress metering, multitenancy, containers, port flapping, jitter, staple/hole-punch finishing issues.
- Gone or no longer listed: the port list is shorter (no SNMP 161/162, no LDAP-S, no TFTP), 802.11 standards are listed only as a heading, the laser imaging process steps are not listed (only laser maintenance), the cloud "desktop as a service"/SDN bullets and long-range fixed wireless licensing detail are not listed, 3-D printers are not listed.

---

## 2. Domain 1.0 — Mobile Devices (13%)

### 1.1 Given a scenario, monitor mobile device hardware and use appropriate replacement techniques
- Battery
- Keyboard / individual keys
- RAM
- HDD / SSD
- Wireless cards
- Physical privacy and security components: biometrics; near-field scanner features
- Wi-Fi antenna connector and placement
- Camera / webcam
- Microphone

*Study pointers:* laptops use SODIMM; many thin laptops have soldered RAM and M.2 SSDs; Wi-Fi antenna leads run up into the display lid; disconnect AC and battery before service; swollen battery = stop using and replace.

### 1.2 Compare and contrast accessories and connectivity options for mobile devices
- Connection methods: USB, USB-C, microUSB, miniUSB; Lightning; NFC; Bluetooth; tethering / hotspot
- Accessories: stylus; headsets; speakers; webcam
- Docking station
- Port replicator
- Trackpad / drawing pad / track points

### 1.3 Given a scenario, configure basic mobile device network connectivity and provide application support
- Wireless / cellular data network (enable/disable): 3G/4G/5G; hotspot; Wi-Fi; SIM / eSIM
- Bluetooth pairing sequence: enable Bluetooth; enable pairing; find the device; enter the PIN code; test connectivity
- Location services: GPS services; cellular location services
- Mobile device management (MDM): device configurations (corporate-owned, BYOD); policy enforcement; corporate applications
- Mobile device synchronization: recognising data caps; calendar; contacts; business applications (mail, cloud storage)

---

## 3. Domain 2.0 — Networking (23%)

### 2.1 Compare and contrast TCP and UDP ports, protocols, and their purposes
- Ports: 20-21 FTP; 22 SSH; 23 Telnet; 25 SMTP; 53 DNS; 67/68 DHCP; 80 HTTP; 110 POP3; 143 IMAP; 137-139 NetBIOS / NetBT; 389 LDAP; 443 HTTPS; 445 SMB/CIFS; 3389 RDP
- TCP vs. UDP (connection-oriented vs. connectionless)

### 2.2 Explain wireless networking technologies
- Frequencies: 2.4GHz, 5GHz, 6GHz
- Channels: regulations; channel selection (widths, frequencies, bands)
- Bluetooth
- 802.11 standards
- NFC
- RFID

*Study pointers:* 802.11a 5GHz/54Mbps; b 2.4/11; g 2.4/54; n (Wi-Fi 4) 2.4+5; ac (Wi-Fi 5) 5 only; ax (Wi-Fi 6) 2.4+5, Wi-Fi 6E adds 6GHz; be (Wi-Fi 7) 2.4+5+6. Non-overlapping 2.4GHz channels: 1, 6, 11.

### 2.3 Summarize services provided by networked hosts
- Server roles: DNS; DHCP; file share; print server; mail server; syslog; web server; AAA; database server; NTP
- Internet appliances: spam gateways; unified threat management (UTM); load balancers; proxy servers
- Legacy / embedded systems: SCADA
- IoT devices

### 2.4 Explain common network configuration concepts
- DNS records: A; AAAA; CNAME; MX; TXT — and spam management through TXT records: DKIM, SPF, DMARC
- DHCP: leases; reservations; scope; exclusions
- VLAN
- VPN

### 2.5 Compare and contrast common networking hardware devices
- Routers
- Switches: managed; unmanaged
- Access points
- Patch panel
- Firewall
- Power over Ethernet: injectors; PoE switch; PoE standards
- Cable modem
- DSL (modem)
- Optical network terminal (ONT)
- Network interface card (NIC); MAC address

*Study pointers:* PoE 802.3af ≈ 15.4W, PoE+ 802.3at ≈ 30W, PoE++ 802.3bt ≈ 60W (Type 3) / up to 100W (Type 4) at the source.

### 2.6 Given a scenario, configure basic wired/wireless SOHO networks
- IP addressing: IPv4 (private addresses, public addresses); IPv6; APIPA; static; dynamic; subnet mask; gateway

### 2.7 Compare and contrast internet connection types, network types, and their characteristics
- Internet connection types: satellite; fiber; cable; DSL; cellular; wireless internet service provider (WISP)
- Network types: LAN; WAN; PAN; MAN; SAN; WLAN

### 2.8 Explain networking tools and their purposes
- Crimper; cable stripper; Wi-Fi analyzer; toner probe; punchdown tool; cable tester; loopback plug; network tap

---

## 4. Domain 3.0 — Hardware (25%)

### 3.1 Compare and contrast display components and attributes
- Types: LCD (IPS, TN, VA); OLED; Mini-LED
- Touch screen / digitizer
- Inverter
- Attributes: pixel density; refresh rate; screen resolution; color gamut

### 3.2 Summarize basic cable types and their connectors, features, and purposes
- Network cables — copper: categories (Cat 5/5e/6/6a ...); T568A / T568B; coaxial; shielded twisted pair (incl. direct burial); unshielded twisted pair; plenum-rated
- Network cables — optical: single-mode; multimode
- Peripheral cables: USB 2.0; USB 3.0; serial; Thunderbolt
- Video cables: HDMI; DisplayPort; DVI; VGA; USB-C
- Hard drive cables: SATA; eSATA
- Adapters
- Connector types: RJ11; RJ45; F-type; ST; SC; LC; punchdown block; microUSB; miniUSB; USB-C; Molex; Lightning; DB9

### 3.3 Compare and contrast RAM characteristics
- Form factors: SODIMM vs. DIMM
- DDR iterations (DDR3 / DDR4 / DDR5 — not interchangeable)
- ECC vs. non-ECC
- Channel configurations (single, dual, triple, quad)

### 3.4 Compare and contrast storage devices
- Hard drives: spindle speeds; form factors (2.5-inch, 3.5-inch)
- Solid-state drives: communications interfaces (NVMe, SATA, PCIe, SAS); form factors (M.2, mSATA)
- Drive configurations: RAID 0, 1, 5, 6, 10
- Removable storage: flash drives; memory cards
- Optical drives

### 3.5 Given a scenario, install and configure motherboards, CPUs, and add-on cards
- Motherboard form factors: ATX; microATX; ITX
- Motherboard connector types: PCI; PCIe; power connectors; SATA; eSATA; headers; M.2
- Motherboard compatibility: CPU socket types (AMD, Intel); multisocket
- BIOS/UEFI settings: boot options; USB permissions; TPM security features; fan considerations; Secure Boot; boot password; BIOS password; temperature monitoring; virtualization support
- Encryption: TPM; hardware security module (HSM)
- CPU architecture: x86 / x64; ARM; core configurations
- Expansion cards: sound card; video card; capture card; NIC
- Cooling: fans; heat sink; thermal paste / pads; liquid

### 3.6 Given a scenario, install the appropriate power supply
- Input 110-120 VAC vs. 220-240 VAC
- Output 3.3V vs. 5V vs. 12V
- 20+4 pin motherboard connector
- Redundant power supply
- Modular power supply
- Wattage rating
- Energy efficiency

### 3.7 Given a scenario, deploy and configure multifunction devices/printers and settings
- Properly unbox the device and consider the set-up location
- Use appropriate drivers for the operating system: PCL vs. PostScript
- Firmware
- Device connectivity: USB; Ethernet; wireless
- Public / shared devices: printer share; print server
- Configuration settings: duplex; orientation; tray settings; quality
- Security: user authentication; badging; audit logs; secured prints
- Network scan services: email; SMB; cloud services
- Automatic document feeder (ADF) / flatbed scanner

### 3.8 Given a scenario, perform appropriate printer maintenance
- Laser: replace toner, apply the maintenance kit, calibrate, clean
- Inkjet: parts (ink cartridge, printhead, roller, feeder); maintenance — clean printheads, replace cartridges, calibrate, clear jams
- Thermal: parts (feed assembly, special thermal paper); maintenance — replace paper, clean the heating element, remove debris
- Impact: multipart paper; maintenance — replace ribbon, printhead and paper

*Study pointers:* the laser imaging process (processing, charging, exposing, developing, transferring, fusing, cleaning) is no longer listed but explains most laser faults in 5.6 and is still worth teaching.

---

## 5. Domain 4.0 — Virtualization and Cloud Computing (11%)

### 4.1 Explain virtualization concepts
- Purpose of virtual machines: sandbox; test development; application virtualization (legacy software/OS, cross-platform virtualization)
- Requirements: security; network; storage
- Desktop virtualization: virtual desktop infrastructure (VDI)
- Containers
- Hypervisors: Type 1; Type 2

### 4.2 Summarize cloud computing concepts
- Common cloud models: private; public; hybrid; community; IaaS; SaaS; PaaS
- Cloud characteristics: shared vs. dedicated resources; metered utilization (ingress / egress); elasticity; availability; file synchronization; multitenancy

---

## 6. Domain 5.0 — Hardware and Network Troubleshooting (28%)

Every objective here is "given a scenario, troubleshoot ..." and lists common symptoms. Authors should pair each symptom with its usual causes and the first sensible check.

### 5.1 Motherboards, RAM, CPUs, and power
- POST beeps; proprietary crash screens (BSOD / pinwheel / kernel panic); blank screen; no power; sluggish performance; overheating; burning smell; random shutdown; application crashes; unusual noise; capacitor swelling; inaccurate system date/time

### 5.2 Drive and RAID issues
- LED status indicators; grinding noises; clicking sounds; bootable device not found; data loss / corruption; RAID failure; S.M.A.R.T. failure; extended read/write times; low IOPS; missing drives in the OS; array missing; audible alarms

### 5.3 Video, projector, and display issues
- Incorrect input source; physical cabling issues; burnt-out bulb; fuzzy image; display burn-in; dead pixels; flashing screen; incorrect color display; audio issues; dim image; intermittent projector shutdown; sizing issues; distorted image

### 5.4 Common mobile device issues
- Poor battery health; swollen battery; broken screen; improper charging; poor / no connectivity; liquid damage; overheating; digitizer issues; physically damaged ports; malware; cursor drift / touch calibration; unable to install new applications; stylus does not work; degraded performance

### 5.5 Network issues
- Intermittent wireless connectivity; slow network speeds; limited connectivity; jitter; poor VoIP quality; port flapping; high latency; external interference; authentication failures; intermittent internet connectivity

### 5.6 Printer issues
- Lines down the printed pages; garbled print; paper jams; faded prints; paper not feeding; multipage misfeed; multiple prints pending in queue; speckling; double / echo images; grinding noise; finishing issues (staple jams, hole punch); incorrect page orientation; tray not recognized; connectivity issues; frozen print queue

---

## 7. Acronyms

The objectives document ends with an acronym list the candidate is expected to
know (AAA, ACL, ADF, AES, APFS, APIPA, ARM, ATX, BIOS, BSOD, BYOD, CMOS, CNAME,
DB-9, DDR, DHCP, DIMM, DKIM, DMARC, DNS, DSL, DVI, ECC, eSATA, ESD and so on
through the alphabet). Part authors writing complete coverage should open the
PDF and check their items against that list; it was not transcribed here.
