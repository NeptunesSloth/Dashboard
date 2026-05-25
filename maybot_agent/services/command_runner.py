from __future__ import annotations

from pathlib import Path
import subprocess
import psutil


def _normalize(command: dict | None) -> dict:
    return command if isinstance(command, dict) else {}


def _safe_cwd(command: dict, project: dict) -> str | None:
    cwd = command.get("cwd") or project.get("path")
    if not cwd:
        return None
    p = Path(cwd)
    return str(p) if p.exists() and p.is_dir() else None


def run_foreground(command: dict | None, project: dict) -> dict:
    cfg = _normalize(command)
    argv = cfg.get("argv")
    if not isinstance(argv, list) or not argv:
        return {"status": "unknown", "output": "command argv not configured"}
    cwd = _safe_cwd(cfg, project)
    timeout_seconds = int(cfg.get("timeout_seconds", 120))
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        output = ((result.stdout or "") + ("\n" + result.stderr if result.stderr else "")).strip()
        return {"status": "ok" if result.returncode == 0 else "error", "code": result.returncode, "output": output}
    except FileNotFoundError:
        return {"status": "error", "output": f"executable not found: {argv[0]}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": f"command timed out after {timeout_seconds}s"}
    except Exception as exc:
        return {"status": "error", "output": str(exc)}


def start_background(command: dict | None, project: dict) -> dict:
    cfg = _normalize(command)
    argv = cfg.get("argv")
    if not isinstance(argv, list) or not argv:
        return {"status": "unknown", "output": "start argv not configured"}
    if cfg.get("background") is not True:
        return {"status": "error", "output": "start command must set background=true"}

    cwd = _safe_cwd(cfg, project)
    stdout_path = cfg.get("stdout")
    stderr_path = cfg.get("stderr")
    pid_file = cfg.get("pid_file") or project.get("pid_file")

    try:
        stdout_handle = None
        stderr_handle = None
        if stdout_path:
            out_p = Path(cwd or ".") / stdout_path
            out_p.parent.mkdir(parents=True, exist_ok=True)
            stdout_handle = out_p.open("a", encoding="utf-8")
        if stderr_path:
            err_p = Path(cwd or ".") / stderr_path
            err_p.parent.mkdir(parents=True, exist_ok=True)
            if stdout_path and stderr_path == stdout_path:
                stderr_handle = subprocess.STDOUT
            else:
                stderr_handle = err_p.open("a", encoding="utf-8")

        proc = subprocess.Popen(argv, cwd=cwd, stdout=stdout_handle or subprocess.DEVNULL, stderr=stderr_handle or subprocess.DEVNULL, text=True)
        if pid_file:
            pid_path = Path(cwd or ".") / pid_file
            pid_path.parent.mkdir(parents=True, exist_ok=True)
            pid_path.write_text(str(proc.pid), encoding="utf-8")
        return {"status": "ok", "pid": proc.pid, "output": "started"}
    except FileNotFoundError:
        return {"status": "error", "output": f"executable not found: {argv[0]}"}
    except Exception as exc:
        return {"status": "error", "output": str(exc)}


def stop_process(command: dict | None, project: dict) -> dict:
    cfg = _normalize(command)
    pid_file = project.get("pid_file") or cfg.get("pid_file")
    token = cfg.get("match_cmdline_contains")
    killed = []
    if pid_file:
        try:
            cwd = _safe_cwd(cfg, project)
            pid = int((Path(cwd or ".") / pid_file).read_text(encoding="utf-8").strip())
            p = psutil.Process(pid)
            p.terminate()
            killed.append(pid)
        except Exception:
            pass
    if token:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if token in cmdline:
                try:
                    psutil.Process(proc.info["pid"]).terminate()
                    killed.append(proc.info["pid"])
                except Exception:
                    pass
    if not killed:
        return {"status": "unknown", "output": "no matching process found"}
    return {"status": "ok", "killed_pids": sorted(set(killed))}
