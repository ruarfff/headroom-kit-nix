"""Run the released wheel with a local dependency fixture and a cold uv cache."""

import functools
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def make_dependency(index: Path) -> str:
    filename = "headroom_ai-0.39.1-py3-none-any.whl"
    info = "headroom_ai-0.39.1.dist-info"
    with zipfile.ZipFile(index / filename, "w") as wheel:
        wheel.writestr(
            f"{info}/METADATA",
            "Metadata-Version: 2.3\nName: headroom-ai\nVersion: 0.39.1\n"
            "Provides-Extra: proxy\nProvides-Extra: code\n",
        )
        wheel.writestr(
            f"{info}/WHEEL", "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        )
        wheel.writestr(f"{info}/RECORD", "")
        wheel.writestr("headroom/__init__.py", "")
        wheel.writestr("headroom/cli/__init__.py", "")
        wheel.writestr("headroom/cli/__main__.py", "print('headroom fixture')\n")
    (index / "index.html").write_text(f'<a href="{filename}">{filename}</a>')
    return filename


def make_environment(root: Path, endpoint: str) -> tuple[dict[str, str], Path, Path]:
    user = root / "config/uv"
    system = root / "system/uv"
    project = root / "project"
    for path in (user, system, project):
        path.mkdir(parents=True)
    (system / "uv.toml").write_text("")
    (user / "uv.toml").write_text(f'[[index]]\nurl = "{endpoint}/user/simple"\ndefault = true\n')
    (project / "uv.toml").write_text(
        f'[[index]]\nurl = "{endpoint}/project/simple"\ndefault = true\n'
    )
    (project / "headroom_kit.py").write_text("raise RuntimeError('project import')\n")
    agent = root / "fake agent"
    agent.write_text(f"#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
    agent.chmod(0o700)
    return (
        {
            "HOME": str(root),
            "PATH": os.defpath,
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_CONFIG_DIRS": str(root / "system"),
            "UV_CACHE_DIR": str(root / "cache"),
            "HTTP_PROXY": endpoint,
            "HTTPS_PROXY": endpoint,
            "ALL_PROXY": endpoint,
            "NO_PROXY": "127.0.0.1",
            "UV_HTTP_RETRIES": "0",
            "UV_HTTP_TIMEOUT": "2",
            "HEADROOM_CODEX_EXECUTABLE": str(agent),
        },
        project,
        agent,
    )


@contextmanager
def local_index(root: Path) -> Iterator[tuple[str, list[str], str]]:
    index = root / "user/simple/headroom-ai"
    index.mkdir(parents=True)
    filename = make_dependency(index)
    requests = []

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            super().do_GET()

        def do_CONNECT(self) -> None:
            requests.append("blocked-external-connect")
            self.send_error(403)

        def log_message(self, format: str, *args: str | int) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(root)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, filename
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


class PackageTest(unittest.TestCase):
    def test_released_cli_and_nix_defaults_with_user_index(self) -> None:
        package = Path(os.environ["HEADROOM_KIT_PACKAGE"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with local_index(root) as (endpoint, requests, filename):
                env, project, agent = make_environment(root, endpoint)

                def run(command: str, *args: str, expected: int = 0) -> str:
                    result = subprocess.run(
                        [str(package / "bin" / command), *args],
                        env=env,
                        cwd=project,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    self.assertEqual(result.returncode, expected, result.stderr)
                    return result.stdout + result.stderr

                self.assertEqual(
                    run("headroom-kit", "--version"), "headroom-kit 0.1.1\nheadroom-ai 0.39.1\n"
                )
                self.assertIn(f"/user/simple/headroom-ai/{filename}", requests)
                self.assertTrue(all(path.startswith("/user/simple/") for path in requests))
                self.assertEqual(run("headroom"), "headroom fixture\n")
                self.assertIn("copilot-auth", run("headroom-kit", "--help"))
                self.assertIn("Agents:", run("headroom-kit", "run", "--help"))
                self.assertEqual(
                    json.loads(run("codex-headroom", "--help", "two words", "")),
                    ["--help", "two words", ""],
                )
                self.assertEqual(
                    json.loads(run("headroom-kit", "run", "codex", "--", "--help")), ["--help"]
                )
                config = root / "custom defaults.json"
                config.write_text(json.dumps({"codexExecutable": str(agent)}))
                del env["HEADROOM_CODEX_EXECUTABLE"]
                original_package = package
                package = Path(os.environ["HEADROOM_KIT_CONFIGURED_PACKAGE"])
                self.assertEqual(run("codex-headroom", "--help"), "")
                self.assertEqual(run("headroom-kit", "run", "codex", "--", "--help"), "")
                env["HEADROOM_CODEX_EXECUTABLE"] = str(agent)
                self.assertEqual(json.loads(run("codex-headroom", "--help")), ["--help"])
                del env["HEADROOM_CODEX_EXECUTABLE"]
                package = original_package
                self.assertEqual(
                    json.loads(
                        run("headroom-kit", "--config", str(config), "run", "codex", "--", "--help")
                    ),
                    ["--help"],
                )
                env["HEADROOM_VERSION"] = "latest"
                self.assertIn(
                    "Runtime selection is no longer supported",
                    run("headroom-kit", "run", "codex", "--", expected=1),
                )

    def test_release_contains_client_resources(self) -> None:
        with zipfile.ZipFile(os.environ["HEADROOM_KIT_WHEEL"]) as wheel:
            for name in (
                "pi-extension.mjs",
                "opencode-plugin/index.js",
                "opencode-plugin/package.json",
            ):
                self.assertIn(f"headroom_kit/resources/{name}", wheel.namelist())


if __name__ == "__main__":
    unittest.main()
