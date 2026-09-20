"""Resolve the selected runtime and preserve foreground process behavior."""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import FrameType
from typing import Never, TypedDict

ENV_OPTIONS = {
    "version": "HEADROOM_VERSION",
    "startupTimeout": "HEADROOM_STARTUP_TIMEOUT",
    "codexExecutable": "HEADROOM_CODEX_EXECUTABLE",
    "codexPort": "HEADROOM_CODEX_PORT",
    "codexAppPath": "HEADROOM_CODEX_APP_PATH",
    "copilotExecutable": "HEADROOM_COPILOT_EXECUTABLE",
    "copilotPort": "HEADROOM_COPILOT_PORT",
    "piExecutable": "HEADROOM_PI_EXECUTABLE",
    "piPort": "HEADROOM_PI_PORT",
    "opencodeExecutable": "HEADROOM_OPENCODE_EXECUTABLE",
    "opencodePort": "HEADROOM_OPENCODE_PORT",
    "vscodeChannel": "HEADROOM_VSCODE_CHANNEL",
    "vscodeExecutable": "HEADROOM_VSCODE_EXECUTABLE",
    "vscodePort": "HEADROOM_VSCODE_PORT",
    "vscodeUserDataDir": "HEADROOM_VSCODE_USER_DATA_DIR",
    "vscodeExtensionsDir": "HEADROOM_VSCODE_EXTENSIONS_DIR",
}


class Config(TypedDict):
    version: str
    startupTimeout: int
    codexExecutable: str
    codexPort: int
    codexAppPath: str | None
    copilotExecutable: str
    copilotPort: int
    piExecutable: str
    piPort: int
    opencodeExecutable: str
    opencodePort: int
    vscodeChannel: str
    vscodeExecutable: str | None
    vscodePort: int
    vscodeUserDataDir: str | None
    vscodeExtensionsDir: str | None
    uv: str
    python: str


type Json = str | int | float | bool | None | list[Json] | dict[str, Json]


class KitError(Exception): ...


def say(message: str) -> None:
    print(f"Headroom Kit: {message}", file=sys.stderr, flush=True)


def stop(signum: int, _frame: FrameType | None) -> Never:
    raise SystemExit(128 + signum)


def terminate(
    process: subprocess.Popen[str] | subprocess.Popen[bytes], group: bool = False
) -> None:
    if process.poll() is None:
        pid = -process.pid if group else process.pid
        try:
            os.kill(pid, signal.SIGTERM)
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.kill(pid, signal.SIGKILL)
            process.wait()
        except ProcessLookupError:
            process.wait()


def run_agent(argv: Sequence[str], env: Mapping[str, str] | None = None) -> int:
    # Same foreground process group and inherited terminal: no stdin proxying.
    child = subprocess.Popen(argv, env=env)
    try:
        code = child.wait()
        return code if code >= 0 else 128 - code
    finally:
        terminate(child)


def configuration(path: str) -> Config:
    cfg = json.loads(Path(path).read_text())
    cfg.update({key: os.environ[var] for key, var in ENV_OPTIONS.items() if var in os.environ})
    return cfg


def validate(cfg: Config) -> None:
    for key, variable in ENV_OPTIONS.items():
        if isinstance(cfg[key], str) and not cfg[key].strip():
            raise KitError(f"{variable} must not be empty. Unset it to use the default.")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+|latest", cfg["version"]):
        raise KitError("HEADROOM_VERSION must be an exact stable X.Y.Z release or latest.")
    validate_numbers(cfg)
    if cfg["vscodeChannel"] not in ("stable", "insiders"):
        raise KitError("HEADROOM_VSCODE_CHANNEL must be stable or insiders.")


def validate_numbers(cfg: Config) -> None:
    ports = ("codexPort", "copilotPort", "vscodePort", "piPort", "opencodePort")
    for key in (*ports, "startupTimeout"):
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            raise KitError(f"{ENV_OPTIONS[key]} must be an integer.") from None
        if key != "startupTimeout" and not 1 <= cfg[key] <= 65535:
            raise KitError(f"{ENV_OPTIONS[key]} must be between 1 and 65535.")
    if cfg["startupTimeout"] < 1:
        raise KitError("HEADROOM_STARTUP_TIMEOUT must be positive.")
    if cfg["codexPort"] in (cfg["copilotPort"], cfg["vscodePort"]):
        raise KitError("Codex and Copilot must use separate ports.")
    for key in ("piPort", "opencodePort"):
        if any(cfg[key] == cfg[other] for other in ports if key != other):
            raise KitError("Pi and OpenCode must use separate ports from other wrappers.")


def executable(value: str | None, variable: str) -> str:
    found = shutil.which(os.path.expanduser(value)) if value else None
    if not found:
        raise KitError(
            f"Agent not found. Install it separately or set {variable} to its executable path."
        )
    return os.path.abspath(found)


def privacy(env: Mapping[str, str]) -> dict[str, str]:
    result = dict(env)
    result.setdefault("HEADROOM_TELEMETRY", "on")
    result.update(
        HEADROOM_BEACON="off",
        HEADROOM_LOG_MESSAGES="off",
        HEADROOM_CODEX_WIRE_DEBUG="off",
        DO_NOT_TRACK="1",
    )
    result.pop("HEADROOM_LOG_FILE", None)
    return result


def resolve(cfg: Config) -> tuple[str, str]:
    requested = cfg["version"]
    spec = "headroom-ai[proxy]" + ("" if requested == "latest" else f"=={requested}")
    args = [
        cfg["uv"],
        "--no-env-file",
        "--isolated",
        "--no-python-downloads",
        "--python",
        cfg["python"],
        "--prerelease",
        "disallow",
        "--from",
        spec,
    ]
    if requested == "latest":
        args += ["--refresh", "--upgrade-package", "headroom-ai"]
    args += [
        "python",
        "-I",
        "-c",
        (
            "import importlib.metadata,json,sys; "
            "print(json.dumps([importlib.metadata.version('headroom-ai'),sys.executable]))"
        ),
    ]
    say(f"Resolving Headroom {requested}; first use requires runtime downloads.")
    # Index errors may contain credentialed URLs. Never copy resolver diagnostics
    # into the terminal or a log. Supply a stable, actionable failure instead.
    child = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=privacy(os.environ),
    )
    try:
        output, _ = child.communicate()
    finally:
        terminate(child)
    if child.returncode:
        raise KitError(
            f"Cannot resolve Headroom {requested} with Nix Python 3.13. "
            "Check the release, network, package index access, and UV_NATIVE_TLS/CA settings. "
            "No alternate version was selected."
        )
    try:
        version, python = json.loads(output)
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ValueError
        if requested != "latest" and version != requested:
            raise ValueError
        if not Path(python).is_absolute() or not os.access(python, os.X_OK):
            raise ValueError
    except (ValueError, TypeError):
        raise KitError(
            "uv returned an incompatible Headroom environment; no agent was launched."
        ) from None
    say(f"Resolved Headroom {version}.")
    return version, python
