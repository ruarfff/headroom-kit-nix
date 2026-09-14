"""Adapted source launcher contracts, extended for Kit's shared lifecycle."""

import contextlib
import importlib
import json
import os
import pty
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "libexec/launch.py"
sys.path.insert(0, str(LAUNCHER.parent))
kit = importlib.import_module("kit_session")
kit_proxy = importlib.import_module("kit_proxy")
STANDIN = Path(__file__).with_name("standin.py").read_text()


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in (
            "uvx",
            "codex",
            "copilot",
            "code",
            "code-insiders",
            "agent with spaces",
        ):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + STANDIN)
            path.chmod(0o755)
        runtime = self.root / "runtime python"
        runtime.write_text(f"#!{sys.executable}\n" + STANDIN)
        runtime.chmod(0o755)
        self.cfg = {
            "version": "0.37.0",
            "startupTimeout": 2,
            "codexExecutable": "codex",
            "codexPort": free_port(),
            "codexAppPath": None,
            "copilotExecutable": "copilot",
            "copilotPort": free_port(),
            "vscodeChannel": "insiders",
            "vscodeExecutable": None,
            "vscodePort": free_port(),
            "vscodeUserDataDir": None,
            "vscodeExtensionsDir": None,
            "uv": str(self.bin / "uvx"),
            "python": sys.executable,
        }
        self.defaults = self.root / "defaults.json"
        self.defaults.write_text(json.dumps(self.cfg))
        # Deliberately do not inherit real runtime configuration or credentials.
        self.env = {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            "KIT_TEST_ROOT": str(self.root),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "VSCODE_IPC_HOOK_CLI": "fake-existing-editor",
            "VSCODE_PORTABLE": "fake-portable",
        }
        self.config = self.root / ".codex/config.toml"
        self.config.parent.mkdir()
        self.original = b'model = "existing-model"\n# Keep all existing preferences\n'
        self.config.write_bytes(self.original)

    def events(self) -> list[dict[str, kit_proxy.Json]]:
        path = self.root / "events"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_launcher(
        self,
        *args: str,
        command: str = "codex-headroom",
        mode: str = "",
        env: dict[str, str] | None = None,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(LAUNCHER), str(self.defaults), command, *args],
            env=dict(self.env, KIT_TEST_MODE=mode, **(env or {})),
            cwd=self.root,
            capture_output=True,
            text=True,
            input=input,
            timeout=15,
        )

    def start(
        self,
        command: str = "codex-headroom",
        mode: str = "wait",
        env: dict[str, str] | None = None,
        args: Sequence[str] = (),
        stdin: int | None = None,
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            [sys.executable, str(LAUNCHER), str(self.defaults), command, *args],
            env=dict(self.env, KIT_TEST_MODE=mode, **(env or {})),
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin,
            text=True,
            start_new_session=True,
        )

        def cleanup() -> None:
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()

        self.addCleanup(cleanup)
        return process

    def wait_for(self, event: str, process: subprocess.Popen[str], count: int = 1) -> None:
        deadline = time.monotonic() + 8
        while len([e for e in self.events() if e["event"] == event]) < count:
            if process.poll() is not None:
                self.fail(process.communicate()[1])
            self.assertLess(time.monotonic(), deadline, f"Timed out waiting for {event}")
            time.sleep(0.02)

    def test_arguments_stdout_stdin_cwd_status_and_normal_config(self) -> None:
        args = ["exec", "--json", "a prompt with spaces and $(literal)"]
        result = self.run_launcher(*args, mode="stdin", input="prompt from stdin\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "AGENT_OUTPUT\nprompt from stdin\n")
        self.assertNotIn("fake-private", result.stderr)
        self.assertEqual(self.config.read_bytes(), self.original)
        event = next(e for e in self.events() if e["event"] == "agent")
        self.assertEqual(event["cwd"], str(self.root))
        self.assertEqual(
            event["args"],
            [
                *args,
                "-c",
                'model_provider="openai"',
                "-c",
                f'openai_base_url="http://127.0.0.1:{self.cfg["codexPort"]}/v1"',
            ],
        )
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")

    def test_codex_config_overrides_share_the_subcommand_scope(self) -> None:
        args = [
            "-c",
            'model_reasoning_effort="low"',
            "exec",
            "--config=model_verbosity=low",
            "-cweb_search=disabled",
            "--",
            "a prompt with --config=literal",
        ]
        result = self.run_launcher(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = next(e for e in self.events() if e["event"] == "agent")["args"]
        # Codex 0.154.0 replaces global -c values when a subcommand has its
        # own -c values. Keep user settings and routing in that same scope.
        self.assertEqual(actual[0], "exec")
        self.assertEqual(actual[-2:], args[-2:])
        settings = dict(value.split("=", 1) for value in actual[2:-2:2])
        self.assertEqual(settings["model_reasoning_effort"], '"low"')
        self.assertEqual(settings["model_verbosity"], "low")
        self.assertEqual(settings["web_search"], "disabled")
        self.assertEqual(settings["model_provider"], '"openai"')
        self.assertEqual(
            settings["openai_base_url"],
            f'"http://127.0.0.1:{self.cfg["codexPort"]}/v1"',
        )

    def test_agent_failure_status_and_cleanup(self) -> None:
        result = self.run_launcher(mode="agent-failure")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")

    def test_cleanup_propagates_process_errors_and_restores_handlers(self) -> None:
        class InaccessibleProcess(subprocess.Popen[bytes]):
            def poll(self) -> int | None:
                raise PermissionError("Cannot inspect proxy process")

        handlers = {
            sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        }
        metadata = self.root / "proxy.json"
        original = json.dumps({"owner": os.getpid()})
        metadata.write_text(original)
        with InaccessibleProcess([sys.executable, "-c", "pass"]) as process:
            with self.assertRaisesRegex(PermissionError, "Cannot inspect proxy process"):
                kit_proxy.cleanup_proxy(process, metadata)
        self.assertEqual(metadata.read_text(), original)
        self.assertEqual({sig: signal.getsignal(sig) for sig in handlers}, handlers)

    def test_help_version_no_resolution_or_state(self) -> None:
        for command in ("codex-headroom", "copilot-headroom"):
            for args in (["--help"], ["--version"], ["exec", "--help"]):
                result = self.run_launcher(
                    *args, command=command, env={"HEADROOM_VERSION": "invalid"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
        for command in ("codex-app-headroom", "copilot-vscode-headroom"):
            self.assertEqual(self.run_launcher("--help", command=command).returncode, 0)
        self.assertTrue(all(e["event"] == "agent" for e in self.events()))
        self.assertFalse((self.root / "state").exists())

    def test_missing_agent_precedes_download(self) -> None:
        result = self.run_launcher(env={"HEADROOM_CODEX_EXECUTABLE": "/missing/agent"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("HEADROOM_CODEX_EXECUTABLE", result.stderr)
        self.assertEqual(self.events(), [])

    def test_executable_with_spaces(self) -> None:
        result = self.run_launcher(
            "a b",
            env={"HEADROOM_CODEX_EXECUTABLE": str(self.bin / "agent with spaces")},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(next(e for e in self.events() if e["event"] == "agent")["args"][0], "a b")

    def test_version_exact_environment_precedence(self) -> None:
        result = self.run_launcher(env={"HEADROOM_VERSION": "0.38.0", "KIT_TEST_VERSION": "0.38.0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Resolved Headroom 0.38.0", result.stderr)
        self.assertIn("headroom-ai[proxy]==0.38.0", self.events()[0]["args"])

    def test_latest_refreshes_disallows_prereleases_and_reports_resolved_version(self) -> None:
        result = self.run_launcher(env={"HEADROOM_VERSION": "latest", "KIT_TEST_VERSION": "0.39.0"})
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.events()[0]["args"]
        for arg in (
            "--refresh",
            "--upgrade-package",
            "headroom-ai",
            "--prerelease",
            "disallow",
            "--no-python-downloads",
        ):
            self.assertIn(arg, args)
        self.assertIn("Resolved Headroom 0.39.0", result.stderr)

    def test_direct_latest_reports_real_version_not_selection_keyword(self) -> None:
        result = self.run_launcher(
            "--version", command="headroom", env={"HEADROOM_VERSION": "latest"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "headroom 0.37.0\n")

    def test_bad_ports_and_conflicting_providers_fail_before_resolution(self) -> None:
        for env in (
            {"HEADROOM_CODEX_PORT": "0"},
            {"HEADROOM_CODEX_PORT": "65536"},
            {"HEADROOM_CODEX_PORT": "bad"},
            {"HEADROOM_CODEX_PORT": str(self.cfg["copilotPort"])},
            {"HEADROOM_STARTUP_TIMEOUT": "0"},
            {"HEADROOM_STARTUP_TIMEOUT": "-1"},
            {"HEADROOM_STARTUP_TIMEOUT": "bad"},
        ):
            self.assertEqual(self.run_launcher(env=env).returncode, 1)
        for args in (
            ["--oss"],
            ["-c", 'model_provider="custom"'],
            ["--config=openai_base_url=somewhere"],
            ["-cmodel_provider=custom"],
        ):
            self.assertEqual(self.run_launcher(*args).returncode, 1)
        self.assertEqual(self.events(), [])

    def test_startup_timeout_is_not_limited_to_port_range(self) -> None:
        result = self.run_launcher(env={"HEADROOM_STARTUP_TIMEOUT": "65536"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")

    def test_http_proxy_environment_cannot_intercept_health(self) -> None:
        result = self.run_launcher(
            env={"HTTP_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_client_proxy_exclusions_preserve_upstream_environment(self) -> None:
        proxy_vars = dict.fromkeys(
            (
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            ),
            "http://127.0.0.1:1",
        )
        cases = (
            ({}, "127.0.0.1,localhost,::1"),
            (
                {"NO_PROXY": "index.example.invalid"},
                "index.example.invalid,127.0.0.1,localhost,::1",
            ),
            (
                {"no_proxy": "internal.example.invalid"},
                "internal.example.invalid,127.0.0.1,localhost,::1",
            ),
            (
                {
                    "NO_PROXY": " index.example.invalid,127.0.0.1",
                    "no_proxy": "internal.example.invalid,localhost",
                },
                "index.example.invalid,127.0.0.1,internal.example.invalid,localhost,::1",
            ),
        )
        for command in ("codex-headroom", "copilot-headroom", "copilot-vscode-headroom"):
            for exclusions, expected in cases:
                with self.subTest(command=command, exclusions=exclusions):
                    inherited = dict(proxy_vars, **exclusions)
                    result = self.run_launcher(command=command, mode="agent-failure", env=inherited)
                    self.assertEqual(result.returncode, 37, result.stderr)
                    child = next(
                        e for e in reversed(self.events()) if e["event"] in ("agent", "editor")
                    )
                    upstream = next(
                        e for e in reversed(self.events()) if e["event"] == "proxy-start"
                    )
                    self.assertEqual(
                        child["proxy_env"], dict(proxy_vars, NO_PROXY=expected, no_proxy=expected)
                    )
                    self.assertEqual(upstream["proxy_env"], inherited)

    def test_client_wildcard_keeps_upstream_proxy_policy(self) -> None:
        inherited = dict.fromkeys(
            ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"),
            "http://127.0.0.1:1",
        )
        inherited.update(NO_PROXY="other.example.invalid", no_proxy="*")
        for command in ("codex-headroom", "copilot-headroom", "copilot-vscode-headroom"):
            with self.subTest(command=command):
                result = self.run_launcher(command=command, mode="agent-failure", env=inherited)
                self.assertEqual(result.returncode, 37, result.stderr)
                child = next(
                    e for e in reversed(self.events()) if e["event"] in ("agent", "editor")
                )
                upstream = next(e for e in reversed(self.events()) if e["event"] == "proxy-start")
                self.assertEqual(child["proxy_env"], {"NO_PROXY": "*", "no_proxy": "*"})
                self.assertEqual(upstream["proxy_env"], inherited)

    def test_client_environment_does_not_mutate_the_caller(self) -> None:
        inherited = {
            "NO_PROXY": "index.example.invalid",
            "no_proxy": "other.example.invalid",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "KEEP_ME": "unchanged",
        }
        original = dict(inherited)
        child = kit.client_environment(inherited)
        self.assertEqual(inherited, original)
        self.assertEqual(child["KEEP_ME"], "unchanged")
        self.assertEqual(child["HTTPS_PROXY"], inherited["HTTPS_PROXY"])
        self.assertEqual(child["NO_PROXY"], child["no_proxy"])
        child["KEEP_ME"] = "child only"
        self.assertEqual(inherited, original)

    def test_healthy_foreign_proxy_without_kit_metadata_is_refused(self) -> None:
        owner = self.start()
        self.wait_for("agent", owner)
        (self.root / "state/headroom-kit" / f"{self.cfg['codexPort']}.json").unlink()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertIn("incompatible", result.stderr)
        self.assertIsNone(owner.poll())

    def test_failed_editor_proxy_does_not_open_editor(self) -> None:
        result = self.run_launcher(command="copilot-vscode-headroom", mode="startup-failure")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(any(e["event"] == "editor" for e in self.events()))

    def test_configurable_extension_path_with_spaces(self) -> None:
        extensions = self.root / "custom extensions"
        result = self.run_launcher(
            command="copilot-vscode-headroom",
            mode="agent-failure",
            env={"HEADROOM_VSCODE_EXTENSIONS_DIR": str(extensions)},
        )
        self.assertEqual(result.returncode, 37, result.stderr)
        event = next(e for e in self.events() if e["event"] == "editor")
        self.assertEqual(
            event["args"][event["args"].index("--extensions-dir") + 1], str(extensions)
        )

    def test_invalid_unavailable_and_incompatible_versions_fail_closed(self) -> None:
        for env in (
            {"HEADROOM_VERSION": "0.37.0rc1"},
            {"KIT_TEST_VERSION": "0.38.0"},
            {"HEADROOM_VERSION": "latest", "KIT_TEST_VERSION": "0.38.0rc1"},
        ):
            result = self.run_launcher(env=env)
            self.assertEqual(result.returncode, 1)
        result = self.run_launcher(mode="download-failure")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No alternate version", result.stderr)
        self.assertNotIn("fake-private", result.stderr)
        self.assertFalse(any(e["event"] == "agent" for e in self.events()))

    def test_startup_failure_wrong_upstream_and_timeout(self) -> None:
        for mode in ("startup-failure", "wrong-upstream", "not-ready"):
            result = self.run_launcher(mode=mode, env={"HEADROOM_STARTUP_TIMEOUT": "1"})
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("not launched", result.stderr)
        self.assertFalse(any(e["event"] == "agent" for e in self.events()))

    def test_occupied_socket_is_not_reused_or_killed(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", self.cfg["codexPort"]))
            listener.listen()
            result = self.run_launcher()
            self.assertEqual(result.returncode, 1)
            self.assertIn("occupied", result.stderr)
            self.assertEqual(listener.getsockname()[1], self.cfg["codexPort"])
        self.assertFalse(any(e["event"] == "proxy-start" for e in self.events()))

    def test_reuse_preserves_proxy_after_agent_failure(self) -> None:
        owner = self.start()
        self.wait_for("agent", owner)
        result = self.run_launcher(mode="agent-failure")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertIn("Reusing", result.stderr)
        self.assertIsNone(owner.poll())
        self.assertEqual(len([e for e in self.events() if e["event"] == "proxy-start"]), 1)
        self.assertFalse(any(e["event"] == "proxy-stop" for e in self.events()))

    def test_explicit_and_latest_version_mismatch_refuse_reuse(self) -> None:
        owner = self.start()
        self.wait_for("agent", owner)
        for version in ("0.38.0", "latest"):
            result = self.run_launcher(
                env={"HEADROOM_VERSION": version, "KIT_TEST_VERSION": "0.38.0"}
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("incompatible", result.stderr)
        self.assertIsNone(owner.poll())

    def test_interrupt_cleans_owned_proxy(self) -> None:
        process = self.start()
        self.wait_for("agent", process)
        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=12)
        self.assertEqual(process.returncode, 130, stderr)
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")
        self.assertTrue(kit_proxy.port_free(self.cfg["codexPort"]))

    def test_reused_proxy_survives_interrupt(self) -> None:
        owner = self.start()
        self.wait_for("agent", owner)
        borrower = self.start()
        self.wait_for("agent", borrower, count=2)
        borrower.terminate()
        borrower.communicate(timeout=12)
        self.assertEqual(borrower.returncode, 143)
        self.assertIsNone(owner.poll())
        self.assertFalse(any(e["event"] == "proxy-stop" for e in self.events()))

    def test_foreground_terminal_is_inherited(self) -> None:
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        process = self.start(stdin=slave)
        self.wait_for("agent", process)
        self.assertTrue(next(e for e in self.events() if e["event"] == "agent")["tty"])

    def test_codex_privacy_and_conservative_flags(self) -> None:
        result = self.run_launcher(env={"HEADROOM_BEACON": "on", "HEADROOM_OUTPUT_SHAPER": "on"})
        self.assertEqual(result.returncode, 0, result.stderr)
        event = next(e for e in self.events() if e["event"] == "proxy-start")
        self.assertEqual(event["cwd"], "/")
        for arg in (
            "--lossless",
            "--disable-kompress",
            "--disable-kompress-fallback",
            "--stateless",
            "--no-telemetry",
            "--no-cache",
            "--no-rate-limit",
            "--no-learn",
        ):
            self.assertIn(arg, event["args"])
        self.assertEqual(event["env"]["HEADROOM_BEACON"], "off")
        self.assertEqual(event["env"]["HEADROOM_OUTPUT_SHAPER"], "off")

    def test_copilot_subscription_responses_and_model_unchanged(self) -> None:
        result = self.run_launcher(
            "--model",
            "chosen-model",
            command="copilot-headroom",
            env={"COPILOT_MODEL": "saved-model"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        event = next(e for e in self.events() if e["event"] == "agent")
        self.assertEqual(event["args"], ["--model", "chosen-model"])
        self.assertEqual(event["env"]["COPILOT_PROVIDER_WIRE_API"], "responses")
        self.assertEqual(event["env"]["COPILOT_MODEL"], "saved-model")
        self.assertNotIn("fake-test-token", result.stdout + result.stderr)

    def test_copilot_auth_failure_no_proxy_or_agent(self) -> None:
        result = self.run_launcher(command="copilot-headroom", mode="auth-failure")
        self.assertEqual(result.returncode, 1)
        self.assertIn("copilot-auth login", result.stderr)
        self.assertNotIn("fake-private", result.stderr)
        self.assertEqual([e["event"] for e in self.events()], ["resolve"])

    def test_editor_isolation_preferences_port_and_cleanup(self) -> None:
        data = self.root / "isolated editor with spaces"
        settings = data / "User/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('// Existing preferences\n{"editor.fontSize": 19}\n')
        project = self.root / "project with spaces"
        project.mkdir()
        process = self.start(
            command="copilot-vscode-headroom",
            mode="",
            args=[str(project)],
            env={
                "HEADROOM_VSCODE_USER_DATA_DIR": str(data),
                "HEADROOM_VSCODE_CHANNEL": "stable",
            },
        )
        self.wait_for("editor", process)
        # Allow the CLI launcher to exit and return control to the proxy wait.
        time.sleep(0.1)
        process.terminate()
        stdout, stderr = process.communicate(timeout=12)
        self.assertEqual(process.returncode, 143, stderr)
        self.assertEqual(stdout, "")
        event = next(e for e in self.events() if e["event"] == "editor")
        self.assertEqual(
            event["args"],
            [
                "--user-data-dir",
                str(data),
                "--extensions-dir",
                str(self.root / ".vscode/extensions"),
                "--sync",
                "off",
                "--new-window",
                str(project),
            ],
        )
        self.assertEqual(event["env"], {})
        self.assertIn("Existing preferences", settings.read_text())
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertIn(f"http://127.0.0.1:{self.cfg['vscodePort']}/dashboard", stderr)
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")

    def test_editor_failure_cleans_proxy(self) -> None:
        result = self.run_launcher(command="copilot-vscode-headroom", mode="agent-failure")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(self.events()[-1]["event"], "proxy-stop")

    def test_duplicate_editor_wrapper_refused(self) -> None:
        process = self.start(command="copilot-vscode-headroom", mode="")
        self.wait_for("editor", process)
        result = self.run_launcher(command="copilot-vscode-headroom")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already running", result.stderr)

    def test_normal_editor_data_rejected_and_untouched(self) -> None:
        base = (
            self.root / "Library/Application Support"
            if sys.platform == "darwin"
            else self.root / "config"
        )
        normal = base / "Code"
        settings = normal / "User/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_bytes(self.original)
        alias = self.root / "alias"
        alias.symlink_to(normal, target_is_directory=True)
        for path in (normal, alias):
            result = self.run_launcher(
                command="copilot-vscode-headroom",
                env={"HEADROOM_VSCODE_USER_DATA_DIR": str(path)},
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(settings.read_bytes(), self.original)
        self.assertEqual(self.events(), [])

    def assert_settings_escape_rejected(
        self, link_user: bool = False, return_inside: bool = False
    ) -> None:
        normal = self.root / "normal Code/User/settings.json"
        normal.parent.mkdir(parents=True)
        original = b'{\n  "editor.fontSize": 19,\n}\n'
        normal.write_bytes(original)
        data = self.root / "isolated Headroom"
        data.mkdir()
        if link_user:
            (data / "User").symlink_to(normal.parent, target_is_directory=True)
            if return_inside:
                inside = data / "preferences.json"
                inside.write_bytes(original)
                normal.unlink()
                normal.symlink_to(inside)
        else:
            (data / "User").mkdir()
            (data / "User/settings.json").symlink_to(normal)
        result = self.run_launcher(
            command="copilot-vscode-headroom",
            mode="agent-failure",
            env={"HEADROOM_VSCODE_USER_DATA_DIR": str(data)},
        )
        self.assertEqual(normal.read_bytes(), original)
        self.assertFalse(any(e["event"] == "editor" for e in self.events()))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("settings path must stay inside", result.stderr)

    def test_editor_settings_symlink_cannot_modify_normal_settings(self) -> None:
        self.assert_settings_escape_rejected()

    def test_editor_user_symlink_cannot_modify_normal_settings(self) -> None:
        self.assert_settings_escape_rejected(link_user=True)

    def test_editor_intermediate_directory_cannot_escape_then_return_inside(self) -> None:
        self.assert_settings_escape_rejected(link_user=True, return_inside=True)

    def test_editor_isolation_arguments_cannot_be_overridden(self) -> None:
        result = self.run_launcher("--user-data-dir=/normal", command="copilot-vscode-headroom")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.events(), [])

    def desktop(self, running: bool = False, platform: str = "darwin") -> kit.Desktop:
        lookup = self.bin / "lookup-app"
        lookup.write_text(
            f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
            f"Path({str(self.root / 'lookup-args')!r}).write_text(repr(sys.argv[1:]))\n"
            + ("print('ASN:existing-app')\n" if running else "")
        )
        lookup.chmod(0o700)
        return kit.Desktop(platform=platform, lookup=str(lookup), open="/stand-in/open")

    def test_app_launch_overrides_and_failure_cleanup(self) -> None:
        events = []
        calls = []

        @contextlib.contextmanager
        def proxy(
            cfg: kit.Config, version: str, kind: str, port: int, auth: kit.CopilotAuth | None
        ) -> Iterator[None]:
            try:
                yield None
            finally:
                events.append("cleanup")

        def launch(argv: Sequence[str], env: Mapping[str, str] | None) -> int:
            calls.append(list(argv))
            return 9

        self.assertEqual(
            kit.session(
                self.cfg,
                "codex-app-headroom",
                [],
                "0.37.0",
                desktop=self.desktop(),
                start_proxy=proxy,
                launch=launch,
            ),
            9,
        )
        self.assertEqual(
            calls,
            [
                [
                    "/stand-in/open",
                    "--env",
                    f"CODEX_APP_SERVER_OPENAI_BASE_URL=http://127.0.0.1:{self.cfg['codexPort']}/v1",
                    "--env",
                    "CODEX_APP_SERVER_FORCE_CLI=1",
                    "-b",
                    "com.openai.codex",
                ]
            ],
        )
        self.assertEqual(events, ["cleanup"])

    def test_running_app_refused_without_quitting(self) -> None:
        with self.assertRaisesRegex(kit.KitError, "Quit Codex first"):
            kit.app_target(self.cfg, self.desktop(running=True))
        self.assertEqual(
            (self.root / "lookup-args").read_text(), repr(["find", "bundleID=com.openai.codex"])
        )

    def test_app_unsupported_platform(self) -> None:
        with self.assertRaisesRegex(kit.KitError, "macOS only"):
            kit.app_target(self.cfg, self.desktop(platform="linux"))
        self.assertFalse((self.root / "lookup-args").exists())

    def test_health_requires_version_upstream_and_ready(self) -> None:
        data = {
            "status": "healthy",
            "ready": True,
            "version": "0.37.0",
            "config": {"openai_api_url": None},
        }
        self.assertTrue(kit_proxy.compatible(data, "0.37.0", None))
        for bad in (
            {**data, "version": "0.38.0"},
            {**data, "ready": False},
            {**data, "config": {}},
            {**data, "config": {"openai_api_url": "https://api.githubcopilot.com"}},
        ):
            self.assertFalse(kit_proxy.compatible(bad, "0.37.0", None))


if __name__ == "__main__":
    unittest.main()
