"""Live share check: real CLIs, real proxies, real provider calls.

Requires every supported coding agent on PATH. Missing tools fail before any
proxy starts. Run from a checkout with Python 3.13 (nix develop).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "libexec/launch.py"
PROMPT = "Reply with the single word ok. Do not run tools."
CLIS = ("codex", "copilot", "pi", "opencode")


def which(name: str) -> str | None:
    found = shutil.which(name)
    return os.path.abspath(found) if found else None


def python313() -> str | None:
    if sys.version_info[:2] == (3, 13):
        return sys.executable
    return which("python3.13")


def vscode() -> str | None:
    return which("code-insiders") or which("code")


def codex_app() -> bool:
    if sys.platform != "darwin":
        return True
    explicit = os.environ.get("HEADROOM_CODEX_APP_PATH")
    apps = (
        [Path(explicit).expanduser()]
        if explicit
        else [
            Path("/Applications/Codex.app"),
            Path("/Applications/ChatGPT.app"),
            Path.home() / "Applications/Codex.app",
            Path.home() / "Applications/ChatGPT.app",
        ]
    )
    for app in apps:
        plist = app / "Contents/Info.plist"
        if not plist.is_file():
            continue
        try:
            result = subprocess.run(
                ["/usr/bin/plutil", "-extract", "CFBundleIdentifier", "raw", str(plist)],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip() == "com.openai.codex":
            return True
    return False


def missing_tools() -> list[str]:
    missing = [name for name in (*CLIS, "uvx") if not which(name)]
    if not python313():
        missing.append("python3.13")
    if not vscode():
        missing.append("code or code-insiders")
    if not codex_app():
        missing.append("Codex macOS app (com.openai.codex)")
    return missing


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def kit_lines(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.startswith("Headroom Kit:")]


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("HEADROOM_")}
    env.update(TERM="dumb", NO_COLOR="1", GIT_TERMINAL_PROMPT="0")
    if extra:
        env.update(extra)
    return env


def run_kit(
    python: str,
    defaults: Path,
    command: str,
    args: list[str],
    env: dict[str, str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [python, "-I", str(LAUNCH), str(defaults), command, *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=240,
    )


def stop(python: str, defaults: Path, env: dict[str, str], port: int) -> None:
    subprocess.run(
        [python, "-I", str(LAUNCH), str(defaults), "headroom-kit", "stop", str(port)],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def arguments(name: str, second: bool) -> list[str]:
    if name == "codex":
        return ["exec", "--skip-git-repo-check", "--sandbox", "read-only", PROMPT]
    if name == "copilot":
        args = ["--model", "gpt-6-astra" if second else "grok-4.6"]
        if second:
            args += ["--reasoning-effort", "high"]
        return [*args, "-p", PROMPT, "-s", "--allow-all-tools"]
    if name == "pi":
        return [
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.6-luna",
            "--no-tools",
            "--no-extensions",
            "-p",
            PROMPT,
        ]
    return ["run", "--model", "opencode/mimo-v2.5-free", PROMPT]


def check(name: str, python: str, defaults: Path, cwd: Path) -> str | None:
    env = child_env()
    try:
        first = run_kit(python, defaults, f"{name}-headroom", arguments(name, False), env, cwd)
    except subprocess.TimeoutExpired:
        return f"{name}: first launch timed out"
    print(*kit_lines(first.stderr), sep="\n")
    if first.returncode or "Started Headroom" not in first.stderr:
        return f"{name}: first launch failed (exit {first.returncode}).\n" + "\n".join(
            first.stderr.splitlines()[-30:]
        )
    extra = (
        {"MallocNanoZone": "0", "OPENAI_API_KEY": "qa-ignored-openai-key"}
        if name == "copilot"
        else None
    )
    try:
        second = run_kit(
            python, defaults, f"{name}-headroom", arguments(name, True), child_env(extra), cwd
        )
    except subprocess.TimeoutExpired:
        return f"{name}: second launch timed out"
    print(*kit_lines(second.stderr), sep="\n")
    if second.returncode or "Reusing Headroom" not in second.stderr:
        return (
            f"{name}: second launch did not reuse the proxy (exit {second.returncode}).\n"
            + "\n".join(second.stderr.splitlines()[-30:])
        )
    print(f"{name}: two real clients, one proxy: PASS", flush=True)
    return None


def main() -> int:
    missing = missing_tools()
    if missing:
        print("QA requires these on PATH / installed:", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        return 1
    python = python313()
    assert python is not None
    editor = vscode()
    assert editor is not None
    ports = {name: free_port() for name in (*CLIS, "vscode")}
    with tempfile.TemporaryDirectory(prefix="headroom-kit-qa-") as temporary:
        cwd = Path(temporary).resolve()
        defaults = cwd / "defaults.json"
        defaults.write_text(
            json.dumps(
                {
                    "version": "0.37.0",
                    "startupTimeout": 180,
                    "codexExecutable": which("codex"),
                    "codexPort": ports["codex"],
                    "codexAppPath": None,
                    "copilotExecutable": which("copilot"),
                    "copilotPort": ports["copilot"],
                    "piExecutable": which("pi"),
                    "piPort": ports["pi"],
                    "opencodeExecutable": which("opencode"),
                    "opencodePort": ports["opencode"],
                    "vscodeChannel": "insiders"
                    if Path(editor).name.endswith("insiders")
                    else "stable",
                    "vscodeExecutable": editor,
                    "vscodePort": ports["vscode"],
                    "vscodeUserDataDir": None,
                    "vscodeExtensionsDir": None,
                    "uv": which("uvx"),
                    "python": python,
                }
            )
        )
        env = child_env()
        failed: list[str] = []
        try:
            for name in CLIS:
                error = check(name, python, defaults, cwd)
                if error:
                    print(error, file=sys.stderr, flush=True)
                    failed.append(name)
        finally:
            for port in ports.values():
                stop(python, defaults, env, port)
        if failed:
            print("QA failed: " + ", ".join(failed), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
