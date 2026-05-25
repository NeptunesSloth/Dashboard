import shlex
import subprocess


def run_configured_command(command: str | None, cwd: str | None = None) -> dict:
    if not command:
        return {"status": "unknown", "output": "command not configured"}
    try:
        result = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        return {"status": "ok" if result.returncode == 0 else "error", "code": result.returncode, "output": output.strip()}
    except Exception as exc:
        return {"status": "error", "output": str(exc)}
