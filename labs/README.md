# Learning Center Lab Targets (phase 3)

Real, Docker-based **pentest / IDS lab targets** for the MayBot Control Center
Learning Center. These let you practice against genuinely vulnerable apps and
then hunt the resulting intrusions in **real** logs — entirely **read-only** from
the dashboard's point of view.

> ## WARNING — intentionally vulnerable
> The apps below (OWASP Juice Shop, DVWA) are **deliberately insecure**. Run them
> **only on an isolated / local network you fully control**. Never expose them to
> the internet, and never attach them to a network with real systems on it. The
> compose file binds every port to `127.0.0.1` for this reason — keep it that way.

## The read-only boundary (read this first)

There are three tiers in the Learning Center, and this lab only touches the first
two:

| Tier | What it is | Status |
|------|-----------|--------|
| **Simulated labs** | The AI invents a synthetic log / CTF scenario and grades your finding. Zero command execution. | Built (`generate_lab` / `grade_lab`). |
| **Real Log Lab (READ-ONLY)** | You attack these targets yourself; their **real** access/auth logs are pulled off a host via a `maybot_agent` and turned into an IDS lab. The dashboard only **reads** logs — it never runs a command. | Built (`fetch_real_logs` -> `generate_real_lab`). **This is what these targets feed.** |
| **Command-execution exploit labs** | Driving recon/exploit commands against a live target from the dashboard. | **Deny-by-default, unbuilt follow-up.** Would have to route through the operator-approved `tools.yaml` / `/api/action` allow-list. LLM text must never become a shell command. See `attach_real_env` in `learning.py`. |

**You** run the targets and **you** generate the attack traffic. The dashboard's
only real-environment interaction is the existing read-only log pull.

## The targets

Defined in `docker-compose.yml` here and catalogued in the repo-root
`lab_targets.yaml` (served by `learning.list_lab_targets()` /
`GET /api/learning/lab/targets`):

- **OWASP Juice Shop** (`juice-shop`, port 3000) — modern vulnerable web app
  (SQLi, broken access control, JWT/session flaws).
- **DVWA** (`dvwa`, port 8080) — classic Damn Vulnerable Web Application (SQLi,
  command injection, XSS, file upload/inclusion). Default creds `admin/password`.
- **log-shipper** (`log-shipper`, port 8088) — an nginx reverse proxy in front of
  the apps that writes access/auth logs to the mounted `./logs` volume so a
  `maybot_agent` can read them into the **Real Log Lab**.

## 1. Run the targets

```bash
docker compose -f labs/docker-compose.yml up
```

Then, from your own machine (isolated network only):

- Juice Shop: <http://127.0.0.1:3000/>
- DVWA: <http://127.0.0.1:8080/> (log in `admin` / `password`, set security to *low*)
- Routed through the logged proxy: <http://127.0.0.1:8088/> (DVWA) and
  <http://127.0.0.1:8088/juice/> (Juice Shop)

Drive your attacks through the **8088** proxy so the traffic is captured in
`labs/logs/access.log`.

## 2. Register the log source as a host/project

So the Learning Center can pull these logs read-only:

1. Run a `maybot_agent` on the host where `labs/logs/` lives, configured to serve
   that directory as a project's logs (same as any other monitored project — see
   the agent docs / `projects.yaml.example`).
2. Add that host to `devices.yaml` and grant your operator token project access.
3. Confirm it shows up in `GET /api/learning/lab/sources` (the host/project pairs
   whose logs can be pulled).

## 3. Hunt intrusions in the real traffic (read-only)

In the Learning Center, open the **Real Log Lab**, pick your registered
host/project, and the AI turns the **real** logs into an intrusion-detection lab:

- API: `POST /api/learning/lab/real` `{ "track": "cybersecurity", "device": "<host>", "project": "<project>" }`
- This calls `fetch_real_logs` (a read-only `GET /api/projects/<project>/logs`
  proxy — **no command execution**) then `generate_real_lab` to build and grade
  the IDS lab.

You attack, the logs record it, and you practice finding your own intrusions in
real data — without the dashboard ever executing anything against the target.

## Browse the catalog

```bash
# module
python -c "from maybot_control_center import learning; print(learning.list_lab_targets())"
# or over HTTP (token-gated)
curl -H "X-Control-Token: <token>" http://127.0.0.1:8000/api/learning/lab/targets
```
