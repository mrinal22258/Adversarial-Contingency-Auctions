"""
Audit logging helper for tracking commands, exit codes, timestamps, and environment.
"""

import os
import sys
import json
import time
import datetime
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AUDIT_DIR = os.path.join(REPO_ROOT, "audit")
LOG_PATH = os.path.join(AUDIT_DIR, "command_log.jsonl")


def log_command(command: str, exit_code: int, stdout: str = "", stderr: str = "", cwd: str = REPO_ROOT, duration_sec: float = 0.0) -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "command": command,
        "exit_code": exit_code,
        "duration_sec": round(duration_sec, 3),
        "cwd": cwd,
        "environment": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "stdout_snippet": (stdout[:1000] if stdout else ""),
        "stderr_snippet": (stderr[:1000] if stderr else "")
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_and_log(cmd_list, cwd=REPO_ROOT, env=None) -> subprocess.CompletedProcess:
    start = time.time()
    cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else str(cmd_list)
    res = subprocess.run(cmd_list, cwd=cwd, env=env, capture_output=True, text=True, shell=isinstance(cmd_list, str))
    dur = time.time() - start
    log_command(cmd_str, res.returncode, stdout=res.stdout, stderr=res.stderr, cwd=cwd, duration_sec=dur)
    return res


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1:]
        res = run_and_log(cmd)
        print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)
