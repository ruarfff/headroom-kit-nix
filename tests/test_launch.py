"""Check the Nix-to-CLI boundary without provider credentials or model calls."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "libexec/launch.py"


class LauncherTest(unittest.TestCase):
    def test_commands_preserve_arguments_working_directory_and_exit_status(self) -> None:
        cases = {
            "headroom": ["savings", "--json"],
            "headroom-kit": ["run", "pi", "--", "--help"],
            "codex-headroom": ["--help", "two words", "", "$(false)"],
            "codex-app-headroom": ["--help"],
            "copilot-headroom": ["--model", "auto"],
            "copilot-vscode-headroom": ["a folder"],
            "pi-headroom": ["--provider", "openai"],
            "opencode-headroom": ["run", "a prompt"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            python = root / "resolved python"
            python.write_text(
                f"#!{sys.executable}\nimport json, os, sys\n"
                "print(json.dumps([sys.argv[1:], os.getcwd()]))\nsys.exit(23)\n"
            )
            python.chmod(0o700)
            uv = root / "uvx"
            uv.write_text(f"#!{sys.executable}\nprint({str(python)!r})\n")
            uv.chmod(0o700)
            for command, args in cases.items():
                with self.subTest(command=command):
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            str(LAUNCHER),
                            str(uv),
                            "wheel",
                            "defaults",
                            command,
                            *args,
                        ],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 23, result.stderr)
                    argv, cwd = json.loads(result.stdout)
                    self.assertEqual(Path(cwd).resolve(), root.resolve())
                    if command == "headroom":
                        expected = ["-I", "-m", "headroom.cli", *args]
                    elif command == "headroom-kit":
                        expected = ["-I", "-m", "headroom_kit", "--config", "defaults", *args]
                    else:
                        expected = [
                            "-I",
                            "-m",
                            "headroom_kit",
                            "--config",
                            "defaults",
                            "run",
                            command.removesuffix("-headroom"),
                            "--",
                            *args,
                        ]
                    self.assertEqual(argv, expected)

    def test_failed_resolution_suppresses_index_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            uv = Path(temporary) / "uvx"
            uv.write_text(
                f"#!{sys.executable}\nimport sys\n"
                "print('private resolver diagnostic', file=sys.stderr)\nsys.exit(1)\n"
            )
            uv.chmod(0o700)
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(LAUNCHER),
                    str(uv),
                    "wheel",
                    "defaults",
                    "headroom-kit",
                    "--version",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Cannot install the pinned Headroom Kit CLI", result.stderr)
            self.assertNotIn("private resolver diagnostic", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
