"""Check cached setup and the Nix-to-CLI boundary without real credentials."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "libexec/launch.py"


class LauncherTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.wheel = self.root / "pinned wheel.whl"
        self.wheel.touch()
        self.calls = self.root / "install calls"
        self.env = {
            **os.environ,
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "UV_AUTH_BACKEND": "system",
            "UV_PREVIEW_FEATURES": "native-auth",
        }
        self.uv = self.root / "uv"
        python_code = (
            f"#!{sys.executable}\nimport json, os, sys\nfrom pathlib import Path\n"
            "if sys.argv[2] == '-c':\n"
            f"    print(json.dumps({{'python': str(Path(sys.executable).resolve()), 'packages': []}}))\n"
            "else:\n"
            "    print(json.dumps([sys.argv[1:], os.getcwd()]))\n"
            "    sys.exit(23)\n"
        )
        self.uv.write_text(
            f"#!{sys.executable}\nimport json, os, sys, time\nfrom pathlib import Path\n"
            f"with open({str(self.calls)!r}, 'a') as log:\n"
            "    log.write(json.dumps([sys.argv[1:], os.environ['UV_AUTH_BACKEND'], "
            "os.environ['UV_PREVIEW_FEATURES']]) + '\\n')\n"
            "directory = Path(os.environ['UV_TOOL_DIR']) / 'headroom-kit/bin'\n"
            "directory.mkdir(parents=True)\n"
            f"python = directory / 'python'\npython.write_text({python_code!r})\n"
            "python.chmod(0o700)\n"
            "gate = os.environ.get('SETUP_GATE')\n"
            "while gate and not Path(gate).exists():\n    time.sleep(0.02)\n"
            "if os.environ.get('SETUP_FAIL'):\n"
            "    print('https://fake-user:fake-secret@index.invalid/', file=sys.stderr)\n"
            "    sys.exit(1)\n"
        )
        self.uv.chmod(0o700)

    def launch(self, command: str = "headroom-kit", *args: str) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(LAUNCHER),
                str(self.uv),
                str(self.wheel),
                "defaults",
                command,
                *args,
            ],
            env=self.env,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)

    def finish(self, process: subprocess.Popen[str], expected: int = 23) -> tuple[str, str]:
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, expected, stderr)
        return stdout, stderr

    def wait_for_setup(self) -> None:
        deadline = time.monotonic() + 5
        while not self.calls.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(self.calls.exists(), "installer did not start")

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
        for command, args in cases.items():
            with self.subTest(command=command):
                stdout, _ = self.finish(self.launch(command, *args))
                argv, cwd = json.loads(stdout)
                self.assertEqual(Path(cwd).resolve(), self.root)
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
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_warm_launch_never_runs_installer_and_preserves_auth_on_setup(self) -> None:
        _, stderr = self.finish(self.launch("headroom-kit", "--version"))
        self.assertIn("Installing", stderr)
        argv, backend, previews = json.loads(self.calls.read_text())
        self.assertEqual(argv[:2], ["tool", "install"])
        self.assertEqual((backend, previews), ("system", "native-auth"))
        self.uv.unlink()
        self.env["UV_OFFLINE"] = "1"
        for _ in range(3):
            _, stderr = self.finish(self.launch("headroom-kit", "--version"))
            self.assertEqual(stderr, "")

    def test_concurrent_setup_publishes_only_after_success(self) -> None:
        gate = self.root / "continue setup"
        self.env["SETUP_GATE"] = str(gate)
        processes = [self.launch("headroom-kit", "--version") for _ in range(4)]
        self.wait_for_setup()
        self.assertFalse(list((self.root / "cache").rglob("ready.json")))
        self.assertTrue(all(process.poll() is None for process in processes))
        gate.touch()
        for process in processes:
            self.finish(process)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)
        self.assertEqual(len(list((self.root / "cache").rglob("ready.json"))), 1)

    def test_failed_setup_hides_diagnostics_and_retries(self) -> None:
        self.env["SETUP_FAIL"] = "1"
        stdout, stderr = self.finish(self.launch(), expected=1)
        self.assertIn("Check", stderr)
        self.assertNotIn("fake-secret", stdout + stderr)
        self.assertNotIn("index.invalid", stdout + stderr)
        self.assertFalse(list((self.root / "cache").rglob("ready.json")))
        del self.env["SETUP_FAIL"]
        self.finish(self.launch())
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)

    def test_interrupted_setup_releases_lock_and_recovers(self) -> None:
        gate = self.root / "continue setup"
        self.env["SETUP_GATE"] = str(gate)
        process = self.launch()
        self.wait_for_setup()
        process.kill()
        process.communicate(timeout=10)
        gate.touch()
        del self.env["SETUP_GATE"]
        self.finish(self.launch())
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)
        self.assertEqual(len(list((self.root / "cache").rglob("env-*"))), 1)

    def test_missing_interpreter_is_rebuilt_without_deleting_complete_generation(self) -> None:
        self.finish(self.launch())
        python = next((self.root / "cache").rglob("headroom-kit/bin/python"))
        python.unlink()
        self.finish(self.launch())
        self.assertTrue(python.parent.exists())
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)

    def test_new_wheel_uses_a_separate_environment(self) -> None:
        self.finish(self.launch())
        self.wheel = self.root / "new wheel.whl"
        self.wheel.touch()
        self.finish(self.launch())
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)
        self.assertEqual(len(list((self.root / "cache").rglob("ready.json"))), 2)


if __name__ == "__main__":
    unittest.main()
