"""maybot-agent command-line helper.

  python -m maybot_agent doctor        # diagnose this host's agent setup
  python -m maybot_agent list-bots     # show configured projects
  python -m maybot_agent add-bot --name X --type trading_bot [--path P] \
                                  [--cmdline-contains S] [--log-file F]

`doctor` is the fast "why isn't my host showing up / why 0 bots" check: it
reports the token state, which projects file is in effect (and how many bots it
holds), and whether the control center URL is reachable. No secrets are printed.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request

from . import config


def _mask(tok: str) -> str:
    if not tok:
        return "(unset)"
    return f"set ({len(tok)} chars, …{tok[-4:]})"


def _reach(url: str) -> str:
    if not url:
        return "MAYBOT_CONTROL_CENTER_URL not set (no self-enroll)"
    test = url.rstrip("/") + "/healthz"
    try:
        with urllib.request.urlopen(test, timeout=8) as r:  # noqa: S310
            return f"reachable (HTTP {r.status})"
    except Exception as exc:  # noqa: BLE001
        return f"NOT reachable: {exc}"


def doctor() -> int:
    token = os.getenv("MAYBOT_API_TOKEN", "")
    control = os.getenv("MAYBOT_CONTROL_CENTER_URL", "")
    pfile = config.PROJECTS_FILE
    exists = pfile.exists()
    try:
        bots = config.load_projects()
        parse = f"{len(bots)} bot(s): {', '.join(str(b.get('name','?')) for b in bots) or '—'}"
    except Exception as exc:  # noqa: BLE001
        parse = f"PARSE ERROR: {exc}"

    print("MayBot agent — doctor")
    print(f"  API token         : {_mask(token)}")
    if not token:
        print("    ! No token set — every /api request returns 401. Set MAYBOT_API_TOKEN.")
    print(f"  Bind port         : {config.PORT}  (uvicorn must use --host 0.0.0.0 to be reachable)")
    print(f"  Projects file     : {pfile}  ({'exists' if exists else 'MISSING — treated as empty'})")
    print(f"  Projects parsed   : {parse}")
    if exists and not bots:
        print("    ! File has no bots. Add some in the dashboard (Hosts → Manage bots), "
              "or `python -m maybot_agent add-bot ...`.")
    print(f"  Control center    : {control or '(unset)'}")
    print(f"  Reachability      : {_reach(control)}")
    return 0


def list_bots() -> int:
    bots = config.load_projects()
    if not bots:
        print(f"No bots configured in {config.PROJECTS_FILE}.")
        return 0
    for b in bots:
        print(f"  - {b.get('name','?')}  [{b.get('type','generic')}]"
              + (f"  path={b.get('path')}" if b.get("path") else ""))
    return 0


def add_bot(args: argparse.Namespace) -> int:
    bots = config.load_projects()
    if any(str(b.get("name")) == args.name for b in bots):
        print(f"A bot named {args.name!r} already exists.", file=sys.stderr)
        return 1
    entry: dict = {"name": args.name, "type": args.type, "expect_running": True}
    if args.path:
        entry["path"] = args.path
    if args.cmdline_contains:
        entry["cmdline_contains"] = args.cmdline_contains
    if args.log_file:
        entry["log_file"] = args.log_file
    bots.append(entry)
    try:
        config.save_projects(bots)
    except ValueError as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 1
    print(f"Added {args.name!r} → {config.PROJECTS_FILE}. The dashboard will show it on the next poll.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maybot_agent", description="MayBot agent helper")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("doctor", help="diagnose this host's agent setup")
    sub.add_parser("list-bots", help="list configured projects")
    add = sub.add_parser("add-bot", help="append a project to projects.yaml")
    add.add_argument("--name", required=True)
    add.add_argument("--type", default="generic")
    add.add_argument("--path")
    add.add_argument("--cmdline-contains", dest="cmdline_contains")
    add.add_argument("--log-file", dest="log_file")

    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "list-bots":
        return list_bots()
    if args.cmd == "add-bot":
        return add_bot(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
