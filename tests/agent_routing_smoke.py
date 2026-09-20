"""Opt-in macOS routing check with real agents, fake keys, and loopback-only networking."""

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SANDBOX = '(version 1)(allow default)(deny network*)(allow network* (local ip "localhost:*") (remote ip "localhost:*"))'


@contextlib.contextmanager
def endpoint() -> Iterator[tuple[int, list[tuple[str, bool, str | None]]]]:
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append(
                (
                    self.path,
                    self.headers.get("Authorization") == "Bearer headroom-kit"
                    and self.headers.get("x-api-key") is None,
                    json.loads(payload).get("model") if payload else None,
                )
            )
            body = b'{"error":{"type":"invalid_request_error","message":"local routing test"}}'
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_CONNECT = do_POST

        def log_message(self, format: str, *args: str | int) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port, requests
        finally:
            server.shutdown()
            thread.join()


@contextlib.contextmanager
def copilot_login(home: Path, model: str | None, credential: str | None) -> Iterator[None]:
    auth = {}
    if credential == "oauth":
        auth["github-copilot"] = {
            "type": "oauth",
            "access": "fake-copilot-access;proxy-ep=proxy.example.invalid",
            "refresh": "fake-copilot-refresh",
            "expires": int(time.time() * 1000) + 3600000,
            "availableModelIds": [model],
        }
    elif credential == "api_key":
        auth["github-copilot"] = {"type": "api_key", "key": "fake-saved-copilot-key"}
    path = home / ".pi/agent/auth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    original = json.dumps(auth).encode()
    path.write_bytes(original)
    yield
    assert path.read_bytes() == original, "Pi credentials changed"


def check(
    agent: str,
    executable: str,
    provider: str,
    mode: str,
    model: str | None = None,
    credential: str | None = None,
) -> None:
    with (
        tempfile.TemporaryDirectory(prefix="headroom-agent-routing-") as temporary,
        copilot_login(Path(temporary), model, credential)
        if provider == "github-copilot"
        else contextlib.nullcontext(),
        endpoint() as (port, cache_requests),
        endpoint() as (copilot_port, copilot_requests),
        endpoint() as (bypass_port, bypassed),
        endpoint() as (forward_port, forwarded),
    ):
        root = Path(temporary).resolve()
        model = model or ("gpt-4.1" if provider == "openai" else "claude-sonnet-4-20250514")
        direct = f"http://127.0.0.1:{bypass_port}/v1"
        env = {
            "HOME": str(root),
            "PATH": "/usr/bin:/bin",
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_DATA_HOME": str(root / "data"),
            "XDG_STATE_HOME": str(root / "state"),
            "XDG_CACHE_HOME": str(root / "cache"),
            "OPENAI_API_KEY": "fake-local-test-key",
            "ANTHROPIC_API_KEY": "fake-local-test-key",
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
            "OPENCODE_DISABLE_MODELS_FETCH": "true",
            "OPENCODE_PRINT_LOGS": "1",
            "TERM": "dumb",
            "NO_COLOR": "1",
        }
        forward = f"http://127.0.0.1:{forward_port}"
        env.update(
            dict.fromkeys(
                (
                    "HTTP_PROXY",
                    "HTTPS_PROXY",
                    "ALL_PROXY",
                    "http_proxy",
                    "https_proxy",
                    "all_proxy",
                ),
                forward,
            )
        )
        if mode == "wildcard":
            env.update(NO_PROXY="example.invalid", no_proxy="*")
        if agent == "pi":
            config = root / ".pi/agent/models.json"
            content = {"providers": {provider: {"baseUrl": direct}}}
            args = [
                "--provider",
                provider,
                "--model",
                model,
                "--no-extensions",
                "--no-skills",
                "--no-session",
                "--no-tools",
                "-p",
                "Reply OK. Do not run tools.",
            ]
        else:
            config = root / "opencode.json"
            content = {
                "model": f"{provider}/{model}",
                "providers": {
                    provider: {
                        "settings": {"baseURL": direct},
                        "models": {model: {"settings": {"baseURL": direct}, "websocket": True}},
                    }
                },
                "permissions": [{"action": "*", "resource": "*", "effect": "deny"}],
            }
            args = [
                "run",
                "--print-logs",
                "--model",
                f"{provider}/{model}",
                "--format",
                "json",
                "Reply OK. Do not run tools.",
            ]
        config.parent.mkdir(parents=True, exist_ok=True)
        original = json.dumps(content).encode()
        config.write_bytes(original)
        cfg = {f"{agent}Executable": executable, f"{agent}Port": port, "copilotPort": copilot_port}
        # A fresh process tests the real inherited environment without patching globals.
        launcher = root / "launch-test.py"
        launcher.write_text(
            "import contextlib, json, os, sys\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / 'libexec')!r})\n"
            "from kit_session import session\n"
            "from kit_proxy import CopilotAuth\n"
            "cfg, command, args = json.loads(sys.argv[1])\n"
            "original = dict(os.environ)\n"
            "session(cfg, command, args, '0.37.0', authorize=lambda: CopilotAuth('https://api.githubcopilot.com', 'fake-headroom-refresh'), start_proxy=lambda *args: 'http://127.0.0.1:' + str(args[3]))\n"
            "assert dict(os.environ) == original\n"
        )
        result = subprocess.run(
            [sys.executable, str(launcher), json.dumps([cfg, f"{agent}-headroom", args])],
            env=env,
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert config.read_bytes() == original
        expected = "/v1/responses" if provider == "openai" else "/v1/messages"
        routed = cache_requests
        if provider == "github-copilot":
            routed = copilot_requests
            assert not cache_requests, "Copilot used the cache proxy"
            assert all(placeholder for _, placeholder, _ in routed), (
                "Copilot token was not replaced"
            )
            if model.startswith("gpt-"):
                expected = "/responses"
            elif model.startswith("gemini-"):
                expected = "/chat/completions"
        assert (
            any(path.split("?", 1)[0] == expected and sent == model for path, _, sent in routed)
            and not bypassed
            and not forwarded
        ), (
            agent,
            provider,
            mode,
            routed,
            bypassed,
            forwarded,
            result.stdout[-2000:],
            [
                line
                for line in result.stderr.splitlines()
                if "plugin" in line or "normalization" in line
            ],
        )
    print(
        f"{agent} {provider} {model} {credential or 'no-login'} {mode}: "
        f"{len(routed)} local requests, no bypass/proxy requests; configuration unchanged",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi", default=shutil.which("pi"))
    parser.add_argument("--opencode", default=shutil.which("opencode"))
    parser.add_argument("--agent", choices=("pi", "opencode"))
    parser.add_argument("--inside-sandbox", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    agents = [("pi", args.pi), ("opencode", args.opencode)]
    agents = [(name, executable) for name, executable in agents if args.agent in (None, name)]
    if sys.platform != "darwin" or any(not executable for _, executable in agents):
        parser.error("macOS and the selected agent executables are required")
    if not args.inside_sandbox:
        os.execv(
            "/usr/bin/sandbox-exec",
            [
                "sandbox-exec",
                "-p",
                SANDBOX,
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                "--inside-sandbox",
            ],
        )
    for agent, executable in agents:
        if agent == "pi":
            for model in ("claude-sonnet-5", "gemini-3.8-flash", "gpt-5.4"):
                for credential in ("oauth", "api_key", None):
                    for mode in ("ordinary", "wildcard"):
                        check(agent, executable, "github-copilot", mode, model, credential)
        for provider in ("openai", "anthropic"):
            for mode in ("ordinary", "wildcard"):
                check(agent, executable, provider, mode)


if __name__ == "__main__":
    main()
