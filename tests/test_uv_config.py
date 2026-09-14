"""Exercise uv's real configuration discovery with a local, synthetic wheel."""

import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from test_launch import LAUNCHER


def make_wheel(index: Path) -> str:
    filename = "headroom_ai-0.37.0-py3-none-any.whl"
    info = "headroom_ai-0.37.0.dist-info"
    with zipfile.ZipFile(index / filename, "w") as wheel:
        wheel.writestr(
            f"{info}/METADATA",
            "Metadata-Version: 2.3\nName: headroom-ai\nVersion: 0.37.0\nProvides-Extra: proxy\n",
        )
        wheel.writestr(
            f"{info}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        wheel.writestr(f"{info}/RECORD", "")
        wheel.writestr("kit_index_fixture.py", 'SOURCE = "temporary-user-index"\n')
    (index / "index.html").write_text(f'<a href="{filename}">{filename}</a>')
    return filename


class UvConfigurationTests(unittest.TestCase):
    def test_user_index_is_used_and_project_index_is_ignored(self) -> None:
        uvx = shutil.which("uvx")
        self.assertIsNotNone(uvx, "This regression requires the real uvx executable.")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            index = root / "user/simple/headroom-ai"
            index.mkdir(parents=True)
            filename = make_wheel(index)
            requests = []

            class Handler(SimpleHTTPRequestHandler):
                def do_GET(self) -> None:
                    requests.append(self.path)
                    super().do_GET()

                def do_CONNECT(self) -> None:
                    # Prevent accidental public-index access even during the red run.
                    requests.append("blocked-external-connect")
                    self.send_error(403)

                def log_message(self, format: str, *args: str | int) -> None:
                    pass

            server = ThreadingHTTPServer(
                ("127.0.0.1", 0), functools.partial(Handler, directory=str(root))
            )
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}"
                user = root / "config/uv"
                system = root / "system/uv"
                project = root / "project"
                for path in (user, system, project):
                    path.mkdir(parents=True)
                (system / "uv.toml").write_text("")
                (user / "uv.toml").write_text(
                    f'[[index]]\nurl = "{endpoint}/user/simple"\ndefault = true\n'
                )
                (project / "uv.toml").write_text(
                    f'[[index]]\nurl = "{endpoint}/project/simple"\ndefault = true\n'
                )
                env = {
                    "HOME": str(root),
                    "PATH": os.defpath,
                    "XDG_CONFIG_HOME": str(root / "config"),
                    "XDG_CONFIG_DIRS": str(root / "system"),
                    "HTTP_PROXY": endpoint,
                    "HTTPS_PROXY": endpoint,
                    "ALL_PROXY": endpoint,
                    "NO_PROXY": "127.0.0.1",
                    "UV_HTTP_RETRIES": "0",
                    "UV_HTTP_TIMEOUT": "2",
                }
                for selection in ("0.37.0", "latest"):
                    with self.subTest(selection=selection):
                        requests.clear()
                        # Cold caches ensure success cannot come from an installed tool.
                        result = subprocess.run(
                            [
                                sys.executable,
                                "-I",
                                "-c",
                                "import sys,json; sys.path.insert(0,sys.argv[1]); "
                                "from kit_runtime import resolve; "
                                "print(json.dumps(resolve(json.loads(sys.argv[2]))))",
                                str(LAUNCHER.parent),
                                json.dumps(
                                    {"uv": uvx, "python": sys.executable, "version": selection}
                                ),
                            ],
                            env=dict(env, UV_CACHE_DIR=str(root / selection)),
                            cwd=project,
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        version, python = json.loads(result.stdout)
                        self.assertEqual(version, "0.37.0")
                        self.assertTrue(Path(python).is_file())
                        self.assertIn(f"/user/simple/headroom-ai/{filename}", requests)
                        self.assertTrue(
                            all(path.startswith("/user/simple/") for path in requests),
                            json.dumps(requests),
                        )
            finally:
                server.shutdown()
                worker.join()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
