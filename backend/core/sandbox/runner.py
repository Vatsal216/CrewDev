import os
import sys
import shlex
import subprocess
from dataclasses import dataclass

_METACHARS = set(";&|`$()<>\n")


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def _limits(mem_mb: int, cpu_secs: int):
    def _apply():
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_secs, cpu_secs))
            b = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (b, b))
        except Exception:
            pass
    return _apply


def run_subprocess(argv: list, cwd: str, timeout: int = 30, mem_mb: int = 1024) -> RunResult:
    preexec = _limits(mem_mb, timeout) if os.name == "posix" else None
    try:
        proc = subprocess.run(
            argv, cwd=cwd, shell=False, capture_output=True, text=True,
            timeout=timeout, preexec_fn=preexec,
        )
    except subprocess.TimeoutExpired:
        return RunResult(stdout="", stderr=f"Timed out after {timeout}s", exit_code=124, timed_out=True)
    except FileNotFoundError as e:
        return RunResult(stdout="", stderr=f"Command not found: {e}", exit_code=127)
    return RunResult(
        stdout=(proc.stdout or "")[:10000],
        stderr=(proc.stderr or "")[:10000],
        exit_code=proc.returncode,
    )


def safe_argv(command: str, allowlist: set) -> list:
    if any(c in command for c in _METACHARS):
        raise ValueError("Command contains disallowed shell metacharacters.")
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty command.")
    if argv[0] not in allowlist:
        raise ValueError(f"Command '{argv[0]}' not in allowlist: {sorted(allowlist)}")
    return argv


def run_python(code: str, run_dir: str, timeout: int = 30, mem_mb: int = 1024):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "main.py"), "w") as f:
        f.write(code)
    before = set(os.listdir(run_dir))
    result = run_subprocess([sys.executable, "main.py"], cwd=run_dir, timeout=timeout, mem_mb=mem_mb)
    after = set(os.listdir(run_dir))
    artifacts = sorted(n for n in (after - before) if n != "main.py")
    return result, artifacts
