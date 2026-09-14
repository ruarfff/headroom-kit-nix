"""Opt-in real runtime check. Uses temporary state and no model credentials."""

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Built headroom-kit store path")
    parser.add_argument("--cache-dir", type=Path, help="Optional reusable uv download cache")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="headroom-kit-runtime-") as temporary:
        root = Path(temporary).resolve()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        agent = root / "stand-in agent"
        agent.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys, urllib.request\n"
            "opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
            "with opener.open('http://127.0.0.1:' + os.environ['HEADROOM_CODEX_PORT'] + '/health') as response:\n"
            "    health = json.load(response)\n"
            "print(json.dumps({'args': sys.argv[1:], 'version': health['version'], 'ready': health['ready'],\n"
            "                  'upstream': health['config']['openai_api_url']}))\n"
        )
        agent.chmod(0o700)
        config = root / ".codex/config.toml"
        config.parent.mkdir()
        original = 'model = "test-only"\n'
        config.write_text(original)
        system_config = root / "system/uv/uv.toml"
        system_config.parent.mkdir(parents=True)
        system_config.write_text("")
        env = {
            "HOME": str(root),
            "PATH": "/usr/bin:/bin",
            "XDG_CONFIG_HOME": str(root / "config"),
            "XDG_CONFIG_DIRS": str(root / "system"),
            "UV_CACHE_DIR": str(args.cache_dir or root / "uv-cache"),
            "HEADROOM_CODEX_EXECUTABLE": str(agent),
            "HEADROOM_CODEX_PORT": str(port),
            "HEADROOM_VERSION": "0.37.0",
        }
        # Deliberately omit the user's environment, token files, and live ports.
        result = subprocess.run(
            [str(args.package / "bin/headroom"), "--version"],
            env=env,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        assert "0.37.0" in result.stdout, result.stdout
        print("Headroom 0.37.0 resolves with Nix Python and uv: PASS")
        result = subprocess.run(
            [str(args.package / "bin/codex-headroom"), "exec", "--json", "stub only"],
            env=env,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["version"] == "0.37.0" and payload["ready"] is True
        assert payload["upstream"] is None
        assert payload["args"] == [
            "exec",
            "--json",
            "stub only",
            "-c",
            'model_provider="openai"',
            "-c",
            f'openai_base_url="http://127.0.0.1:{port}/v1"',
        ]
        assert config.read_text() == original
        with socket.socket() as listener:
            assert listener.connect_ex(("127.0.0.1", port)) != 0
        print(
            "Real Codex proxy readiness, routing arguments, clean JSON, configuration preservation, cleanup: PASS"
        )
        uvx = shutil.which("uvx")
        if uvx is None:
            parser.error("uvx is required; run this smoke test inside nix develop")
        subprocess.run(
            [
                uvx,
                "--isolated",
                "--no-env-file",
                "--no-python-downloads",
                "--python",
                sys.executable,
                "--from",
                "headroom-ai[proxy]==0.37.0",
                "python",
                "-I",
                str(Path(__file__).with_name("smoke_writer.py").resolve()),
            ],
            env=env,
            cwd=root,
            check=True,
            timeout=300,
        )
        # Home/state is discarded; cache reuse is explicit and contains no auth.
        assert not (root / ".headroom/copilot-auth.json").exists()
    return 0


if __name__ == "__main__":
    sys.exit(main())
