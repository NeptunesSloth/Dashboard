# CompTIA A+ Core 2 blueprint (220-1202, "V15") — state as of 25 November 2026

Researcher notes for course authors. This file is the syllabus for the
`a-plus-core2` course: every objective and every listed topic is here,
paraphrased and regrouped from CompTIA's objectives document. Topic lists in
that document are explicitly "not exhaustive", so treat this as the minimum.

Source-quality legend:
- **[VENDOR]** = read this session on CompTIA's own page or official objectives PDF.
- **[3P]** = third-party source only.
- **[RECALL]** = author's own knowledge, not opened this session.

## 1. Exam facts

| Fact | Value | Source |
|---|---|---|
| Exam | CompTIA A+ Core 2 | [VENDOR] |
| Exam code | **220-1202** (series "V15"; paired with Core 1 220-1201 — both must be passed for A+) | [VENDOR] |
| Launch date | 25 March 2025 | [VENDOR] landing page |
| Retirement | "Usually three years after launch" (estimated 2028); no fixed date published | [VENDOR] landing page |
| Number of questions | Maximum of 90 | [VENDOR] both |
| Question types | Multiple-choice (single and multiple response), drag-and-drop and performance-based | [VENDOR] landing page; the PDF says "multiple-choice and performance-based" |
| Length | 90 minutes | [VENDOR] both |
| Passing score | 700 on a scale of 100-900 (a scaled score, not 78%) | [VENDOR] both |
| Recommended experience | 12 months of hands-on experience in an IT support specialist role (a recommendation, not a prerequisite) | [VENDOR] both |
| Languages | English, German, Japanese | [VENDOR] landing page (as summarised by the fetch tool; spot-check before quoting) |
| Windows scope | Windows versions still in Microsoft mainstream support, up to and including Windows 11; objectives that name no version cover Windows 10 and 11 | [VENDOR] PDF |

Domain weights [VENDOR, both sources agree]:

| Domain | Title | Weight |
|---|---|---|
| 1.0 | Operating Systems | 28% |
| 2.0 | Security | 28% |
| 3.0 | Software Troubleshooting | 23% |
| 4.0 | Operational Procedures | 21% |

Objective count: 36 (11 / 11 / 4 / 10).

Sources:
- CompTIA A+ Core 2 V15 landing page: https://www.comptia.org/en-us/certifications/a/core-2-v15/
  (read through a summarising fetch tool, not as raw HTML).
- "CompTIA A+ Core 2 (220-1202) V15 Certification Exam — Exam Objectives
  Document Version 4.0", copyright 2024 CompTIA, served from CompTIA's own
  download host: https://lecbyo.files.cmp.optimizely.com/download/cefedfb2b8a511ef809306d06d323538
  (full text extracted and read this session; all objective lists below come from it).

Unverified / caveats:
- No exact retirement date exists yet; "2028" is CompTIA's estimate.
- Whether a newer objectives-document revision than 4.0 exists was not checked;
  CompTIA revises wording without changing the exam code.
- The in-app trial settings (25 questions / 25 minutes / 85% pass, 90/90 full
  mock) are this app's own choices, not CompTIA facts.

Changes from the previous exam (220-1102) worth knowing when reusing old
material [VENDOR PDF for the content; the comparison itself is RECALL]: weights
moved (OS 31→28, Security 25→28, Software Troubleshooting 22→23, Operational
Procedures 22→21); new objectives for cloud productivity tools (1.11) and AI
basics (4.10); additions such as ReFS and XFS, zero-touch deployment,
stalkerware/fileless/cryptominer malware, EDR/MDR/XDR, QR-code phishing, BEC,
supply-chain attacks, SAML/SSO/PAM/just-in-time access, Zero Trust, passwordless
sign-in, SPICE and WinRM, synthetic full backups, MNDA, change types. The
malware-removal procedure now has ten listed steps.

---

## 2. Domain 1.0 — Operating Systems (28%)

**1.1 Explain common OS types and their purposes.**
- Workstation OSs: Windows, Linux, macOS, Chrome OS.
- Mobile OSs: iPadOS, iOS, Android.
- Filesystems: NTFS, ReFS, FAT32, ext4, XFS, APFS, exFAT.
- Vendor life-cycle limits: end-of-life (EOL), update limitations.
- Compatibility concerns between operating systems.

**1.2 Given a scenario, perform OS installations and upgrades in a diverse environment.**
- Boot methods: USB, network, solid-state/flash drive, internet-based, external/hot-swappable drive, internal hard drive (partition), multiboot.
- Installation types: clean install, upgrade, image deployment, remote network installation, zero-touch deployment, recovery partition, repair installation; other considerations (third-party drivers).
- Partitioning: GPT, MBR.
- Drive format.
- Upgrade considerations: back up files and user preferences; application and driver support / backward compatibility; hardware compatibility.
- Feature updates: product life cycle.

**1.3 Compare and contrast basic features of Microsoft Windows editions.**
- Windows 10 editions: Home, Pro, Pro for Workstations, Enterprise.
- Windows 11 editions: Home, Pro, Enterprise.
- N versions.
- Feature differences: domain vs workgroup, desktop styles/user interface, availability of RDP, RAM support limits, BitLocker, gpedit.msc.
- Upgrade paths: in-place upgrade, clean install.
- Hardware requirements: TPM, UEFI.

**1.4 Given a scenario, use Microsoft Windows operating system features and tools.**
- Task Manager tabs: Services, Startup, Performance, Processes, Users.
- MMC snap-ins: Event Viewer (eventvwr.msc), Disk Management (diskmgmt.msc), Task Scheduler (taskschd.msc), Device Manager (devmgmt.msc), Certificate Manager (certmgr.msc), Local Users and Groups (lusrmgr.msc), Performance Monitor (perfmon.msc), Group Policy Editor (gpedit.msc).
- Additional tools: System Information (msinfo32.exe), Resource Monitor (resmon.exe), System Configuration (msconfig.exe), Disk Cleanup (cleanmgr.exe), Disk Defragment (dfrgui.exe), Registry Editor (regedit.exe).

**1.5 Given a scenario, use the appropriate Microsoft command-line tools.**
- Navigation: cd, dir.
- Network: ipconfig, ping, netstat, nslookup, net use, tracert, pathping.
- Disk management: chkdsk, format, diskpart.
- File management: md, rmdir, robocopy.
- Informational: hostname, net user, winver, whoami, `[command] /?`.
- OS management: gpupdate, gpresult, sfc.

**1.6 Given a scenario, configure Microsoft Windows settings.**
- Control Panel items: Internet Options, Devices and Printers, Programs and Features, Network and Sharing Center, System, Windows Defender Firewall, Mail, Sound, User Accounts, Device Manager, Indexing Options, Administrative Tools.
- File Explorer Options: view hidden files, hide extensions, general options, view options.
- Power Options: hibernate, power plans, sleep/suspend, standby, choose what closing the lid does, turn on fast startup, USB selective suspend.
- Ease of Access.
- Settings app categories: Time and Language, Update and Security, Personalization, Apps, Privacy, System, Devices, Network and Internet, Gaming, Accounts.

**1.7 Given a scenario, configure Microsoft Windows networking features on a client/desktop.**
- Domain-joined vs workgroup: shared resources, printers, file servers, mapped drives.
- Local OS firewall settings: application restrictions and exceptions, configuration.
- Client network configuration: IP addressing scheme, DNS settings, subnet mask, gateway, static vs dynamic.
- Establishing connections: VPN, wireless, wired, WWAN/cellular.
- Proxy settings.
- Public vs private network.
- File Explorer navigation by network path.
- Metered connections and limitations.

**1.8 Explain common features and tools of the macOS/desktop operating system.**
- Installing and uninstalling applications: file types .dmg, .pkg, .app; App Store; uninstallation process.
- System folders: /Applications, /Users, /Library, /System, /Users/Library.
- Apple ID and corporate restrictions.
- Best practices: backups, antivirus, updates/patches, Rapid Security Response (RSR).
- System Preferences: Displays, Networks, Printers, Scanners, Privacy, Accessibility, Time Machine.
- Features: multiple desktops, Mission Control, Keychain, Spotlight, iCloud (iMessage, FaceTime, Drive), gestures, Finder, Dock, Continuity.
- Disk Utility, FileVault, Terminal, Force Quit.

**1.9 Identify common features and tools of the Linux client/desktop operating system.**
- File management: ls, pwd, mv, cp, rm, chmod, chown, grep, find.
- Filesystem management: fsck, mount.
- Administrative: su, sudo.
- Package management: apt, dnf.
- Network: ip, ping, curl, dig, traceroute.
- Informational: man, cat, top, ps, du, df.
- Text editors: nano.
- Common configuration files: /etc/passwd, /etc/shadow, /etc/hosts, /etc/fstab, /etc/resolv.conf.
- OS components: systemd, kernel, bootloader.
- Root account.

**1.10 Given a scenario, install applications according to requirements.**
- System requirements: 32-bit vs 64-bit dependent applications, dedicated vs integrated graphics, VRAM, RAM, CPU, external hardware tokens, storage, application-to-OS compatibility.
- Distribution methods: physical media vs mountable ISO file, downloadable package, image deployment.
- Impact considerations for new applications: device, network, operation, business.

**1.11 Given a scenario, install and configure cloud-based productivity tools.**
- Email systems.
- Storage: sync/folder settings.
- Collaboration tools: spreadsheets, videoconferencing, presentation tools, word processing tools, instant messaging.
- Identity synchronization.
- Licensing assignment.

---

## 3. Domain 2.0 — Security (28%)

**2.1 Summarize various security measures and their purposes.**
- Physical security: bollards, access control vestibule, badge reader, video surveillance, alarm systems, motion sensors, door locks, equipment locks, security guards, fences.
- Physical access security: key fobs, smart cards, mobile digital key, keys, biometrics (retina scanner, fingerprint scanner, palm print scanner, facial recognition technology, voice recognition technology), lighting, magnetometers.
- Logical security: principle of least privilege; Zero Trust model; ACLs; MFA (email, hardware token, authenticator application, SMS, voice call, TOTP, OTP); SAML; SSO; just-in-time access (privileged access management, PAM); MDM; DLP; IAM; directory services.

**2.2 Given a scenario, configure and apply basic Microsoft Windows OS security settings.**
- Defender Antivirus: activate/deactivate, update definitions.
- Firewall: activate/deactivate, port security, application security.
- Users and groups: local vs Microsoft account, standard account, administrator, guest user, power user.
- Log-in options: username and password, PIN, fingerprint, facial recognition, SSO, passwordless/Windows Hello.
- NTFS vs share permissions: file and folder attributes, inheritance.
- Run as administrator vs standard user; User Account Control (UAC).
- BitLocker, BitLocker To Go, Encrypting File System (EFS).
- Active Directory: joining a domain, assigning log-in scripts, moving objects within organizational units, assigning home folders, applying Group Policy, selecting security groups, configuring folder redirection.

**2.3 Compare and contrast wireless security protocols and authentication methods.**
- Protocols and encryption: WPA2, WPA3, TKIP, AES.
- Authentication: RADIUS, TACACS+, Kerberos, multifactor.

**2.4 Summarize types of malware and tools/methods for detection, removal, and prevention.**
- Malware: trojan, rootkit, virus, spyware, ransomware, keylogger, boot sector virus, cryptominer, stalkerware, fileless; adware and potentially unwanted programs (PUPs).
- Tools and methods: recovery console, EDR, MDR, XDR, antivirus, anti-malware, email security gateway, software firewalls, user education on common threats (anti-phishing training), OS reinstallation.

**2.5 Compare and contrast common social engineering attacks, threats, and vulnerabilities.**
- Social engineering: phishing (vishing, smishing, QR code phishing, spear phishing, whaling), shoulder surfing, tailgating, impersonation, dumpster diving.
- Threats: DoS, DDoS, evil twin, zero-day attack, spoofing, on-path attack, brute-force attack, dictionary attack, insider threat, SQL injection, XSS, business email compromise (BEC), supply chain/pipeline attack.
- Vulnerabilities: non-compliant systems, unpatched systems, unprotected systems (missing antivirus/firewall), EOL, BYOD.

**2.6 Given a scenario, implement procedures for basic SOHO malware removal.** The ten listed steps, in order:
1. Investigate and verify malware symptoms.
2. Quarantine the infected system.
3. Disable System Restore in Windows Home.
4. Remediate infected systems.
5. Update anti-malware software.
6. Scan and removal techniques (safe mode, preinstallation environment).
7. Reimage/reinstall.
8. Schedule scans and run updates.
9. Enable System Restore and create a restore point in Windows Home.
10. Educate the end user.

**2.7 Given a scenario, apply workstation security options and hardening techniques.**
- Data-at-rest encryption.
- Password considerations: length, character types, uniqueness, complexity, expiration.
- BIOS/UEFI passwords.
- End-user best practices: screensaver locks, log off when not in use, secure/protect critical hardware (laptops), secure PII and passwords, use password managers.
- Account management: restrict user permissions, restrict log-in times, disable guest account, failed-attempts lockout, timeout/screen lock, account expiration dates.
- Change the default administrator account/password.
- Disable AutoRun.
- Disable unused services.

**2.8 Given a scenario, apply common methods for securing mobile devices.**
- Hardening: device encryption; screen locks (facial recognition, PIN codes, fingerprint, pattern, swipe); configuration profiles.
- Patch management: OS updates, application updates.
- Endpoint security software: antivirus, anti-malware, content filtering.
- Locator applications; remote wipes; remote backup applications; failed log-in attempt restrictions.
- Policies and procedures: MDM, BYOD vs corporate-owned devices, profile security requirements.

**2.9 Compare and contrast common data destruction and disposal methods.**
- Physical destruction of hard drives: drilling, shredding, degaussing, incineration.
- Recycling or repurposing: erasing/wiping, low-level formatting, standard formatting.
- Outsourcing: third-party vendor, certification of destruction/recycling.
- Regulatory and environmental requirements.

**2.10 Given a scenario, apply security settings on SOHO wireless and wired networks.**
- Router settings: change default passwords, IP filtering, firmware updates, content filtering, physical placement/secure location, UPnP, screened subnet, secure management access.
- Wireless-specific: changing the SSID, disabling SSID broadcast, encryption settings, guest access.
- Firewall settings: disabling unused ports, port forwarding/mapping.

**2.11 Given a scenario, configure relevant security settings in a browser.**
- Browser download/installation: trusted sources (hashing), untrusted sources.
- Browser patching.
- Extensions and plug-ins: trusted vs untrusted sources.
- Password managers.
- Secure connections/sites: valid certificates.
- Settings: pop-up blocker, clearing browsing data, clearing cache, private-browsing mode, sign-in/browser data synchronization, ad blockers, proxy, secure DNS.
- Browser feature management: enable/disable plug-ins, extensions, features.

---

## 4. Domain 3.0 — Software Troubleshooting (23%)

**3.1 Given a scenario, troubleshoot common Windows OS issues.**
- Blue screen of death (BSOD), degraded performance, boot issues, frequent shutdowns, services not starting, applications crashing, low memory warnings, USB controller resource warnings, system instability, no OS found, slow profile load, time drift.
- (The V15 document lists symptoms only; the usual remedies — reboot, restart services, uninstall/reinstall/update applications, add resources, verify requirements, sfc, repair/restore/reimage, roll back updates, rebuild profiles — are still what scenario questions ask for. [RECALL])

**3.2 Given a scenario, troubleshoot common mobile OS and application issues.**
- Application fails to launch; fails to close/crashes; fails to update; fails to install.
- Slow to respond; OS fails to update; battery life issues; random reboots.
- Connectivity issues: Bluetooth, Wi-Fi, NFC.
- Screen does not autorotate.

**3.3 Given a scenario, troubleshoot common mobile OS and application security issues.**
- Security concerns: application source/unofficial application stores, developer mode, root access/jailbreak, unauthorized/malicious application (application spoofing).
- Common symptoms: high network traffic, degraded response time, data-usage limit notification, limited internet connectivity, no internet connectivity, high number of ads, fake security warnings, unexpected application behaviour, leaked personal files/data.

**3.4 Given a scenario, troubleshoot common PC security issues.**
- Common symptoms: unable to access the network; desktop alerts; false alerts regarding antivirus protection; altered system or personal files (missing/renamed files, inability to access files); unwanted notifications within the OS; OS update failures.
- Browser-related symptoms: random/frequent pop-ups, certificate warnings, redirection, degraded browser performance.

---

## 5. Domain 4.0 — Operational Procedures (21%)

**4.1 Given a scenario, implement best practices associated with documentation and support systems information management.**
- Ticketing systems: user information, device information, description of issues, categories, severity, escalation levels; clear, concise written communication (issue description, progress notes, issue resolution).
- Asset management: inventory lists, configuration management database (CMDB), asset tags and IDs, procurement life cycle, warranty and licensing, assigned users.
- Types of documents: incident reports; standard operating procedures (e.g. a custom software-package installation procedure); new-user/onboarding setup checklist; user off-boarding checklist; service-level agreements (internal, external/third-party); knowledge base/articles.

**4.2 Given a scenario, apply change management procedures.**
- Documented business processes: rollback plan, backup plan, sandbox testing, responsible staff members.
- Change management: request forms; purpose of the change; scope of the change; change type (standard, normal, emergency); date and time of change (change freeze, maintenance windows); affected systems/impact; risk analysis (risk level); change board approvals; implementation; peer review; end-user acceptance.

**4.3 Given a scenario, implement workstation backup and recovery methods.**
- Backup: full, incremental, differential, synthetic full.
- Recovery: in-place/overwrite, alternative location.
- Backup testing: frequency.
- Backup rotation schemes: onsite vs offsite, grandfather-father-son (GFS), 3-2-1 backup rule.

**4.4 Given a scenario, use common safety procedures.**
- ESD straps, ESD mats.
- Electrical safety: equipment grounding.
- Proper component handling and storage; cable management; antistatic bags.
- Compliance with government regulations.
- Personal safety: disconnect power before repairing a PC, lifting techniques, fire safety, safety goggles, air filter mask.

**4.5 Summarize environmental impacts and local environment controls.**
- MSDS documentation for handling and disposal: proper battery disposal, proper toner disposal, proper disposal of other devices and assets.
- Temperature, humidity-level awareness and proper ventilation: location/equipment placement, dust cleanup, compressed air/vacuums.
- Power surges, brownouts and blackouts: UPS, surge suppressor.

**4.6 Explain the importance of prohibited content/activity and privacy, licensing, and policy concepts.**
- Incident response: chain of custody, informing management/law enforcement as necessary, copy of drive (data integrity and preservation), incident documentation, order of volatility.
- Licensing/DRM/EULA: valid licenses, perpetual license agreement, personal-use vs corporate-use license, open-source license.
- NDA / mutual NDA (MNDA).
- Regulated data: credit card payment information, personal government-issued information, PII, healthcare data, data retention requirements.
- Acceptable use policy (AUP).
- Regulatory and business compliance requirements: splash screens.

**4.7 Given a scenario, use proper communication techniques and professionalism.**
- Professional appearance and attire matched to the environment (formal, business casual).
- Proper language; avoid jargon, acronyms and slang where applicable.
- Positive attitude, project confidence.
- Actively listen; avoid interrupting.
- Cultural sensitivity; appropriate professional titles and designations.
- Be on time; if late, contact the customer.
- Avoid distractions: personal calls, texting/social media, personal interruptions.
- Difficult customers or situations: do not argue or be defensive; do not dismiss the issue; do not be judgmental; clarify statements (open-ended questions to narrow scope, restate the issue, question to verify understanding); use discretion when discussing experiences.
- Set and meet expectations/timeline and communicate status: offer repair/replacement options, provide documentation of services, follow up later to verify satisfaction.
- Handle customers' confidential and private materials appropriately (on a computer, desktop, printer, etc.).

**4.8 Explain the basics of scripting.**
- Script file types: .bat, .ps1, .vbs, .sh, .js, .py.
- Use cases: basic automation, restarting machines, remapping network drives, installing applications, automated backups, gathering information/data, initiating updates.
- Other considerations: unintentionally introducing malware, inadvertently changing system settings, browser or system crashes from mishandled resources.

**4.9 Given a scenario, use remote access technologies.**
- Methods/tools: RDP, VPN, VNC, SSH, remote monitoring and management (RMM), SPICE, Windows Remote Management (WinRM), third-party tools (screen-sharing software, videoconferencing software, file transfer software, desktop management software).
- Security considerations of each access method.

**4.10 Explain basic concepts related to artificial intelligence (AI).**
- Application integration.
- Policy: appropriate use, plagiarism.
- Limitations: bias, hallucinations, accuracy.
- Private vs public: data security, data source, data privacy.

---

## 6. Notes for authors

- The objectives document also carries an acronym list and a proposed
  hardware/software list; neither adds testable objectives and they are not
  reproduced here.
- Scenario verbs matter: "Given a scenario" objectives (1.2, 1.4-1.7, 1.10,
  1.11, 2.2, 2.6-2.8, 2.10, 2.11, all of 3.x, 4.1-4.4, 4.7, 4.9) are where
  performance-based questions come from; write `order`, `multi` and scenario
  `mcq` items against them.
- The base course file `sect_academy/packs/a_plus_core2.yaml` uses unit ids
  `ap2-<domain><letter>`; part files should continue the same prefix scheme with
  new unit ids.
