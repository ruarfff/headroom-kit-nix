"""Executable stand-ins: no real agents, accounts, or model endpoints."""

import json
import os
import runpy
import signal
import socket
import sys
import time
import types
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import FrameType
from typing import Never

type Json = str | int | float | bool | None | list[Json] | dict[str, Json]

ROOT = Path(os.environ["KIT_TEST_ROOT"])
MODE = os.environ.get("KIT_TEST_MODE", "")
PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
)


def record(event: str, **values: Json) -> None:
    with (ROOT / "events").open("a") as file:
        file.write(json.dumps(dict(event=event, **values)) + "\n")


def resolve_runtime() -> int:
    record("resolve", args=sys.argv[1:])
    if MODE == "download-failure":
        print("fake-private-index-diagnostic", file=sys.stderr)
        return 8
    print(
        json.dumps(
            [
                os.environ.get("KIT_TEST_VERSION", "0.37.0"),
                str(ROOT / "runtime python"),
            ]
        )
    )
    return 0


def run_agent(name: str) -> int:
    is_editor = name.startswith("code") and name != "codex"
    event = "editor" if is_editor else "agent"
    record(
        event,
        args=sys.argv[1:],
        proxy_env={key: os.environ[key] for key in PROXY_VARIABLES if key in os.environ},
        pid=os.getpid(),
        cwd=os.getcwd(),
        tty=os.isatty(0),
        env={
            k: os.environ[k]
            for k in os.environ
            if k.startswith("COPILOT_PROVIDER_")
            or k
            in (
                "COPILOT_API_URL",
                "COPILOT_MODEL",
                "HEADROOM_KIT_ENDPOINT",
                "HEADROOM_KIT_COPILOT_ENDPOINT",
                "OPENCODE_CONFIG_CONTENT",
                "VSCODE_IPC_HOOK_CLI",
                "VSCODE_PORTABLE",
            )
        },
    )
    if name == "opencode" and sys.argv[1:] == ["--version"]:
        print(os.environ.get("KIT_TEST_OPENCODE_VERSION", "opencode v2.0.3"))
        return 0
    if not is_editor:
        print("AGENT_OUTPUT", flush=True)
    if MODE == "stdin":
        print(sys.stdin.read(), end="")
    if MODE in ("traffic", "wait-traffic"):
        client_traffic(name)
    if MODE in ("wait", "wait-traffic"):
        while True:
            if MODE == "wait-traffic":
                client_traffic(name)
            if (
                os.environ.get("KIT_TEST_EXIT_FILE")
                and Path(os.environ["KIT_TEST_EXIT_FILE"]).exists()
            ):
                break
            time.sleep(0.1)
    return 37 if MODE == "agent-failure" else 0


def client_traffic(name: str) -> None:
    endpoint = os.environ.get("COPILOT_API_URL") or os.environ.get("HEADROOM_KIT_ENDPOINT")
    if name == "codex":
        endpoint = next(
            arg.split("=", 1)[1].strip('"')
            for arg in sys.argv
            if arg.startswith("openai_base_url=")
        )
    elif name == "opencode":
        endpoint = json.loads(os.environ["OPENCODE_CONFIG_CONTENT"])["plugins"][-1]["options"][
            "endpoint"
        ]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(endpoint + "/responses", data=b"{}", method="POST")
    with opener.open(request, timeout=2) as response:
        record(
            "client-response",
            client=os.environ.get("KIT_TEST_CLIENT", "default"),
            **json.load(response),
        )


def serve_proxy() -> int:
    args = (
        sys.argv[sys.argv.index("__serve") + 2 :]
        if "__serve" in sys.argv
        else sys.argv[sys.argv.index("-m") + 2 :]
    )
    if args == ["--version"]:
        print("headroom " + os.environ.get("HEADROOM_VERSION", "0.37.0"))
        return 0
    record(
        "proxy-start",
        pid=os.getpid(),
        args=args,
        proxy_env={key: os.environ[key] for key in PROXY_VARIABLES if key in os.environ},
        cwd=os.getcwd(),
        env={
            k: os.environ.get(k)
            for k in (
                "HEADROOM_BEACON",
                "HEADROOM_TELEMETRY",
                "HEADROOM_LOG_MESSAGES",
                "HEADROOM_STATELESS",
                "HEADROOM_WORKSPACE_DIR",
                "HEADROOM_SAVINGS_PATH",
                "HEADROOM_SAVINGS_EVENTS_PATH",
                "HEADROOM_OUTPUT_SHAPER",
                "HEADROOM_EFFORT_ROUTER",
                "HEADROOM_VERBOSITY_AUTOTUNE",
                "DO_NOT_TRACK",
            )
        },
    )
    print("fake-private-proxy-diagnostic", flush=True)
    if MODE == "startup-failure":
        return 7
    port = int(args[args.index("--port") + 1])
    upstream = args[args.index("--openai-api-url") + 1] if "--openai-api-url" in args else None
    if MODE == "wrong-upstream":
        upstream = "https://unrelated.example.invalid"
    ready_at = time.monotonic() + float(os.environ.get("KIT_TEST_DELAY", "0.15"))

    count = 0

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            nonlocal count
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            count += 1
            data = json.dumps({"instance": os.getpid(), "count": count}).encode()
            probe = next(
                (
                    value
                    for value in ("shared-probe-one", "shared-probe-two")
                    if value.encode() in body
                ),
                "auxiliary",
            )
            record("proxy-request", instance=os.getpid(), count=count, probe=probe)
            if MODE == "real-routing":
                data = b'{"error":{"type":"invalid_request_error","message":"local routing test"}}'
            self.send_response(400 if MODE == "real-routing" else 200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            data = json.dumps(
                {
                    "status": "healthy",
                    "ready": MODE != "not-ready" and time.monotonic() >= ready_at,
                    "version": os.environ.get("KIT_TEST_VERSION", "0.37.0"),
                    "config": {"openai_api_url": upstream},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: str | int) -> None:
            pass

    if "__serve" in sys.argv:
        server = HTTPServer(("127.0.0.1", port), Handler, bind_and_activate=False)
        server.socket.close()
        server.socket = socket.socket(fileno=int(sys.argv[sys.argv.index("__serve") + 1]))
        server.server_address = server.socket.getsockname()
    else:
        server = HTTPServer(("127.0.0.1", port), Handler)

    def stop(signum: int, frame: FrameType | None) -> Never:
        server.server_close()
        record("proxy-stop")
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    server.serve_forever()
    return 0


def run_session() -> int:
    # Execute the real session code in the simulated resolved environment.
    sys.executable = str(ROOT / "runtime python")
    fake = types.ModuleType("headroom.copilot_auth")

    def auth() -> types.SimpleNamespace:
        if MODE == "auth-failure":
            print("fake-private-auth-diagnostic")
            raise ValueError("fake-private-auth-diagnostic")
        return types.SimpleNamespace(
            api_url="https://api.githubcopilot.com",
            token=os.environ.get("KIT_TEST_ACCESS_TOKEN", "fake-test-token"),
            refresh_oauth_token=os.environ.get("KIT_TEST_ACCOUNT", "fake-refresh-account-one"),
            api_token_expires_at=None,
        )

    fake.resolve_subscription_bearer_token_details = auth
    sys.modules["headroom.copilot_auth"] = fake
    click = types.ModuleType("click")
    click.ClickException = ValueError
    sys.modules["click"] = click
    provider = types.ModuleType("headroom.providers.copilot")

    def configure(path: Path, endpoint: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = path.read_text() if path.exists() else "{}"
        path.write_text(content + "\n// Fake Headroom block: " + endpoint)

    provider.configure_vscode_proxy_settings = configure
    sys.modules["headroom.providers.copilot"] = provider
    sys.argv = sys.argv[2:]  # remove executable and -I
    runpy.run_path(sys.argv[0], run_name="__main__")

    return 0


def main() -> int:
    name = Path(sys.argv[0]).name
    if name == "uvx":
        return resolve_runtime()
    if name in ("codex", "copilot", "pi", "opencode", "agent with spaces", "code", "code-insiders"):
        return run_agent(name)
    if "-m" in sys.argv or "__serve" in sys.argv:
        return serve_proxy()
    return run_session()


if __name__ == "__main__":
    sys.exit(main())
