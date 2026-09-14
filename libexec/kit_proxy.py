"""Own proxy identity, readiness, subscription auth, and cleanup."""

import contextlib
import fcntl
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from kit_runtime import Config, Json, KitError, privacy, say, terminate


@dataclass(frozen=True)
class CopilotAuth:
    api_url: str
    token: str
    refresh_oauth_token: str | None
    api_token_expires_at: float | None


def health(port: int) -> dict[str, Json]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            data = json.loads(response.read(65536))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def compatible(data: dict[str, Json], version: str, upstream: str | None) -> bool:
    config = data.get("config")
    return (
        isinstance(config, dict)
        and data.get("status") == "healthy"
        and data.get("ready") is True
        and data.get("version") == version
        and "openai_api_url" in config
        and config["openai_api_url"] == upstream
    )


def port_free(port: int) -> bool:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


@contextlib.contextmanager
def locked(path: Path, message: str) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise KitError(message) from None
        yield


def proxy_environment(kind: str) -> dict[str, str]:
    # Inherited tuning must not defeat the tested policy or change the upstream.
    blocked = {"OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "PYTHONPATH", "PYTHONHOME"}
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in blocked
        and not key.startswith(("HEADROOM_", "GITHUB_COPILOT_"))
        and not key.endswith("TARGET_API_URL")
    }
    env = privacy(env, local_stats=kind == "copilot")
    env.update(HEADROOM_AGENT_TYPE=kind, HEADROOM_STATELESS="1")
    if kind == "codex":
        env.update(
            HEADROOM_OUTPUT_SHAPER="off",
            HEADROOM_EFFORT_ROUTER="off",
            HEADROOM_VERBOSITY_AUTOTUNE="off",
        )
    return env


def copilot_auth() -> CopilotAuth:
    # The upstream adapter is intentionally narrow; no upstream wrapper lifecycle
    # (which can restart existing proxies or edit normal agent config) is used.
    try:
        from headroom.copilot_auth import resolve_subscription_bearer_token_details
    except ImportError:
        raise KitError(
            "This Headroom release lacks the required Copilot subscription API. "
            "Select HEADROOM_VERSION=0.37.0."
        ) from None
    try:
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            resolution = resolve_subscription_bearer_token_details()
        if resolution is None:
            raise ValueError
        parsed = urllib.parse.urlsplit(resolution.api_url)
        if (
            parsed.scheme != "https"
            or not (parsed.hostname or "").endswith(".githubcopilot.com")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        # Check the complete contract before launching any process.
        return CopilotAuth(
            api_url=resolution.api_url,
            token=resolution.token,
            refresh_oauth_token=resolution.refresh_oauth_token,
            api_token_expires_at=resolution.api_token_expires_at,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        raise KitError(
            "Copilot subscription authorization failed or its endpoint is unsupported. "
            "Run `headroom copilot-auth login`, check your subscription, and retry. "
            "Only HTTPS *.githubcopilot.com upstreams are supported."
        ) from None


def proxy_args(kind: str, port: int, upstream: str | None) -> list[str]:
    args = [
        sys.executable,
        "-I",
        "-m",
        "headroom.cli",
        "proxy",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--stateless",
        "--no-learn",
    ]
    if kind == "codex":
        args += [
            "--mode",
            "cache",
            "--lossless",
            "--disable-kompress",
            "--disable-kompress-fallback",
            "--no-telemetry",
            "--no-cache",
            "--no-rate-limit",
        ]
    else:
        args += ["--openai-api-url", upstream, "--telemetry"]
    return args


@contextlib.contextmanager
def proxy(
    cfg: Config, version: str, kind: str, port: int, auth: CopilotAuth | None = None
) -> Iterator[subprocess.Popen[bytes] | None]:
    upstream = auth.api_url if auth else None
    state = (
        Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "headroom-kit"
    )
    metadata = state / f"{port}.json"
    signature = hashlib.sha256(
        b"".join(path.read_bytes() for path in sorted(Path(__file__).parent.glob("*.py")))
    ).hexdigest()
    identity = {"version": version, "policy": signature, "kind": kind}
    process = None
    try:
        with locked(
            state / f"{port}.lock",
            f"Port {port} is being started by another Kit launcher. Retry shortly.",
        ):
            if not port_free(port):
                try:
                    recorded = json.loads(metadata.read_text())
                    os.kill(recorded["owner"], 0)
                except (OSError, ValueError, KeyError, TypeError):
                    recorded = {}
                if (
                    kind == "codex"
                    and all(recorded.get(k) == v for k, v in identity.items())
                    and compatible(health(port), version, upstream)
                ):
                    say(f"Reusing Headroom {version} on port {port}; keep its owner terminal open.")
                else:
                    raise KitError(
                        f"Port {port} is occupied by an unrelated or incompatible proxy. "
                        "Stop it in its owner terminal or select another port. "
                        "Copilot proxies are private to each launch."
                    )
            else:
                env = proxy_environment(kind)
                if auth:
                    env.update(
                        GITHUB_COPILOT_API_TOKEN=auth.token,
                        GITHUB_COPILOT_API_URL=auth.api_url,
                    )
                    if auth.refresh_oauth_token:
                        env["GITHUB_COPILOT_REFRESH_OAUTH_TOKEN"] = auth.refresh_oauth_token
                    if auth.api_token_expires_at is not None:
                        env["GITHUB_COPILOT_API_TOKEN_EXPIRES_AT"] = str(auth.api_token_expires_at)
                process = subprocess.Popen(
                    proxy_args(kind, port, upstream),
                    env=env,
                    cwd="/",
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                await_ready(process, cfg, version, port, upstream)
                metadata.write_text(json.dumps(dict(identity, owner=os.getpid())))
        say(f"Dashboard: http://127.0.0.1:{port}/dashboard")
        yield process
    finally:
        if process is not None:
            cleanup_proxy(process, metadata)


def await_ready(
    process: subprocess.Popen[bytes], cfg: Config, version: str, port: int, upstream: str | None
) -> None:
    deadline = time.monotonic() + cfg["startupTimeout"]
    while True:
        if process.poll() is not None:
            raise KitError(
                f"Headroom {version} exited before readiness on port {port}. "
                "Check port availability and runtime compatibility; try HEADROOM_VERSION=0.37.0. "
                "The agent was not launched."
            )
        if compatible(health(port), version, upstream):
            return
        if time.monotonic() >= deadline:
            raise KitError(
                f"Headroom did not become ready with the expected version and upstream "
                f"on port {port}. The agent was not launched."
            )
        time.sleep(0.1)


def cleanup_proxy(process: subprocess.Popen[bytes], metadata: Path) -> None:
    # Cleanup cannot be interrupted by a second signal halfway through.
    previous = {
        s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    try:
        terminate(process, group=True)
        with contextlib.suppress(ValueError, OSError):
            if json.loads(metadata.read_text()).get("owner") == os.getpid():
                metadata.unlink()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
