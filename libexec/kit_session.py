"""Route each client for one launch without changing its normal configuration."""

import contextlib
import os
import plistlib
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from kit_proxy import CopilotAuth, copilot_auth, locked, proxy
from kit_runtime import (
    Config,
    KitError,
    configuration,
    executable,
    privacy,
    resolve,
    run_agent,
    say,
    validate,
)


@dataclass(frozen=True)
class Desktop:
    platform: str = sys.platform
    lookup: str = "/usr/bin/lsappinfo"
    open: str = "/usr/bin/open"


type Proxy = Callable[
    [Config, str, str, int, CopilotAuth | None],
    AbstractContextManager[subprocess.Popen[bytes] | None],
]
type Agent = Callable[[Sequence[str], Mapping[str, str] | None], int]


def app_target(cfg: Config, desktop: Desktop = Desktop()) -> list[str]:
    if desktop.platform != "darwin":
        raise KitError("codex-app-headroom supports macOS only. Use codex-headroom on Linux.")
    bundle = "com.openai.codex"
    target = ["-b", bundle]
    if cfg["codexAppPath"]:
        path = Path(cfg["codexAppPath"]).expanduser().resolve()
        try:
            with (path / "Contents/Info.plist").open("rb") as file:
                bundle = plistlib.load(file)["CFBundleIdentifier"]
        except (OSError, ValueError, KeyError):
            raise KitError(
                "HEADROOM_CODEX_APP_PATH must point to an installed macOS app bundle."
            ) from None
        target = ["-a", str(path)]
    if subprocess.run(
        [desktop.lookup, "find", f"bundleID={bundle}"], capture_output=True, text=True, check=True
    ).stdout.strip():
        raise KitError(
            "Quit Codex first, then rerun codex-app-headroom. "
            "An existing app cannot receive new launch settings."
        )
    return target


def editor_paths(cfg: Config) -> tuple[Path, Path]:
    insiders = cfg["vscodeChannel"] == "insiders"
    name = "Code - Insiders" if insiders else "Code"
    base = (
        Path.home() / "Library/Application Support"
        if sys.platform == "darwin"
        else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    )
    data = Path(cfg["vscodeUserDataDir"] or base / f"{name} Headroom").expanduser().resolve()
    # Check both channels and symlinks. Arbitrary custom normal directories cannot
    # be inferred: the documented contract requires a dedicated directory.
    for channel in ("Code", "Code - Insiders"):
        normal = (base / channel).resolve()
        if data == normal or data in normal.parents or normal in data.parents:
            raise KitError(
                "HEADROOM_VSCODE_USER_DATA_DIR must be separate from normal VS Code data."
            )
    extensions = (
        Path(
            cfg["vscodeExtensionsDir"]
            or Path.home() / (".vscode-insiders/extensions" if insiders else ".vscode/extensions")
        )
        .expanduser()
        .resolve()
    )
    editor_settings(data)
    return data, extensions


def editor_settings(data: Path) -> Path:
    """Check each path component before handing a destination to Headroom."""
    settings = data / "User/settings.json"
    try:
        if data.resolve() != data or any(
            not path.resolve().is_relative_to(data) for path in (settings.parent, settings)
        ):
            raise ValueError
        return settings.resolve()
    except (OSError, RuntimeError, ValueError):
        raise KitError(
            "The VS Code settings path must stay inside the isolated user-data directory. "
            "Remove escaping User/settings.json or User directory symlinks, or choose a dedicated directory."
        ) from None


def configure_editor(data: Path, port: int) -> None:
    # Startup can take time. Recheck immediately before the real writer.
    settings = editor_settings(data)
    try:
        from click import ClickException
        from headroom.providers.copilot import configure_vscode_proxy_settings
    except ImportError:
        raise KitError(
            "This Headroom release lacks the editor writer; select HEADROOM_VERSION=0.37.0."
        ) from None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            configure_vscode_proxy_settings(settings, f"http://127.0.0.1:{port}")
    except (ClickException, OSError, RuntimeError, TypeError, ValueError):
        raise KitError(
            "Cannot configure isolated editor settings. Check JSONC/Headroom marker conflicts, "
            "or select HEADROOM_VERSION=0.37.0."
        ) from None


def preflight(
    cfg: Config, command: str, args: list[str], desktop: Desktop = Desktop()
) -> str | list[str] | None:
    if command == "codex-headroom":
        options = args[: args.index("--")] if "--" in args else args
        for index, arg in enumerate(options):
            if arg in ("--oss", "--local-provider"):
                raise KitError("codex-headroom supports only the built-in OpenAI provider.")
            setting = (
                args[index + 1]
                if arg in ("-c", "--config") and index + 1 < len(args)
                else arg.removeprefix("--config=")
                if arg.startswith("--config=")
                else arg[2:]
                if arg.startswith("-c") and arg != "-c"
                else ""
            )
            key = setting.split("=", 1)[0].strip()
            if key in ("model_provider", "openai_base_url") or key.startswith("model_providers."):
                raise KitError(
                    "Provider and endpoint overrides conflict with codex-headroom routing. "
                    "Use the normal codex command for custom providers."
                )
        agent = executable(cfg["codexExecutable"], "HEADROOM_CODEX_EXECUTABLE")
    elif command == "copilot-headroom":
        agent = executable(cfg["copilotExecutable"], "HEADROOM_COPILOT_EXECUTABLE")
    elif command == "codex-app-headroom":
        if args:
            raise KitError("Use codex-app-headroom without arguments, or --help.")
        agent = app_target(cfg, desktop)
    elif command == "copilot-vscode-headroom":
        if len(args) > 1 or (args and args[0].startswith("-")):
            raise KitError(
                "Use copilot-vscode-headroom [path]. Configure isolation through HEADROOM_VSCODE_*."
            )
        agent = executable(
            cfg["vscodeExecutable"]
            or ("code-insiders" if cfg["vscodeChannel"] == "insiders" else "code"),
            "HEADROOM_VSCODE_EXECUTABLE",
        )
        editor_paths(cfg)
    else:
        agent = None
    return agent


def wait_gui(process: subprocess.Popen[bytes] | None) -> int:
    if process is None:
        return 0
    say("Keep this terminal open. Close the wrapped app before Ctrl+C stops its proxy.")
    process.wait()
    raise KitError("Headroom stopped. Close the wrapped app and restart the wrapper.")


def codex_arguments(args: list[str], endpoint: str) -> list[str]:
    # Codex 0.154.0 replaces global -c values when a subcommand supplies -c.
    # Collect all overrides into the final option scope, before a literal --.
    options = []
    overrides = []
    index = 0
    while index < len(args) and args[index] != "--":
        arg = args[index]
        if arg in ("-c", "--config"):
            if index + 1 == len(args):
                raise KitError(f"{arg} requires a key=value argument.")
            index += 1
            overrides += ["-c", args[index]]
        elif arg.startswith("--config="):
            overrides += ["-c", arg.removeprefix("--config=")]
        elif arg.startswith("-c"):
            overrides += ["-c", arg[2:]]
        else:
            options.append(arg)
        index += 1
    return [
        *options,
        *overrides,
        "-c",
        'model_provider="openai"',
        "-c",
        f'openai_base_url="{endpoint}"',
        *args[index:],
    ]


def client_environment(env: Mapping[str, str]) -> dict[str, str]:
    """Keep local client traffic direct without changing upstream proxy policy."""
    child = dict(env)
    exclusions = [
        entry.strip()
        for key in ("NO_PROXY", "no_proxy")
        for entry in env.get(key, "").split(",")
        if entry.strip()
    ]
    if "*" in exclusions:
        # Some clients require an exact "*"; Codex also needs proxy variables removed.
        for key in ("http_proxy", "https_proxy", "all_proxy"):
            child.pop(key, None)
            child.pop(key.upper(), None)
        child.update(NO_PROXY="*", no_proxy="*")
        return child
    bypass = ",".join(dict.fromkeys([*exclusions, "127.0.0.1", "localhost", "::1"]))
    child.update(NO_PROXY=bypass, no_proxy=bypass)
    return child


def session(
    cfg: Config,
    command: str,
    args: list[str],
    version: str,
    *,
    desktop: Desktop = Desktop(),
    authorize: Callable[[], CopilotAuth] = copilot_auth,
    start_proxy: Proxy = proxy,
    launch: Agent = run_agent,
) -> int:
    agent = preflight(cfg, command, args, desktop)
    os.umask(0o077)
    if command.startswith("codex"):
        port = cfg["codexPort"]
        with start_proxy(cfg, version, "codex", port, None) as process:
            endpoint = f"http://127.0.0.1:{port}/v1"
            if command == "codex-headroom":
                return launch(
                    [agent, *codex_arguments(args, endpoint)], client_environment(os.environ)
                )
            # Recheck after a possibly slow download/start to avoid attaching to
            # an app that was opened during startup.
            target = app_target(cfg, desktop)
            result = launch(
                [
                    desktop.open,
                    "--env",
                    f"CODEX_APP_SERVER_OPENAI_BASE_URL={endpoint}",
                    "--env",
                    "CODEX_APP_SERVER_FORCE_CLI=1",
                    *target,
                ],
                None,
            )
            return result or wait_gui(process)
    port = cfg["copilotPort"] if command == "copilot-headroom" else cfg["vscodePort"]
    auth = authorize()
    if command == "copilot-headroom":
        with start_proxy(cfg, version, "copilot", port, auth):
            env = client_environment(os.environ)
            env.pop("COPILOT_PROVIDER_API_KEY", None)
            env.update(
                COPILOT_PROVIDER_TYPE="openai",
                COPILOT_PROVIDER_BASE_URL=f"http://127.0.0.1:{port}/v1",
                COPILOT_PROVIDER_WIRE_API="responses",
                COPILOT_PROVIDER_BEARER_TOKEN=auth.token,
                GITHUB_COPILOT_USE_TOKEN_EXCHANGE="false",
                GITHUB_COPILOT_API_URL=auth.api_url,
                OPENAI_TARGET_API_URL=auth.api_url,
            )
            return launch([agent, *args], env)
    data, extensions = editor_paths(cfg)
    with (
        locked(
            data / ".headroom-launcher.lock",
            "The Headroom editor wrapper is already running. Use its window.",
        ),
        start_proxy(cfg, version, "copilot", port, auth) as process,
    ):
        configure_editor(data, port)
        env = client_environment(os.environ)
        for key in ("VSCODE_IPC_HOOK_CLI", "VSCODE_PORTABLE"):
            env.pop(key, None)
        result = launch(
            [
                agent,
                "--user-data-dir",
                str(data),
                "--extensions-dir",
                str(extensions),
                "--sync",
                "off",
                "--new-window",
                str(Path(args[0] if args else ".").resolve()),
            ],
            env,
        )
        return result or wait_gui(process)


def main() -> int:
    defaults, command, *args = sys.argv[1:]
    cfg = configuration(defaults)
    if command == "__session":
        version, command, *args = args
        validate(cfg)
        return session(cfg, command, args, version)
    if command in ("codex-app-headroom", "copilot-vscode-headroom") and args in (
        ["--help"],
        ["-h"],
    ):
        print(f"Usage: {command}" + (" [path]" if command == "copilot-vscode-headroom" else ""))
        print(
            "Launch with a local Headroom proxy. Keep the owner terminal open; Ctrl+C stops its proxy."
        )
        print(
            "Normal Codex and VS Code launches keep their existing settings. Configure through HEADROOM_*."
        )
        return 0
    options = args[: args.index("--")] if "--" in args else args
    if command in ("codex-headroom", "copilot-headroom") and any(
        arg in ("--help", "-h", "--version", "-V") for arg in options
    ):
        return run_agent([preflight(cfg, command, args), *args])
    validate(cfg)
    preflight(cfg, command, args)
    version, python = resolve(cfg)
    env = dict(os.environ)
    if command == "headroom":
        # Headroom itself also reads this name as a build-version override.
        # Kit owns selection; do not let "latest" replace its reported version.
        env.pop("HEADROOM_VERSION", None)
        os.execve(python, [python, "-I", "-m", "headroom.cli", *args], privacy(env))
    os.execve(
        python,
        [
            python,
            "-I",
            str(Path(__file__).with_name("launch.py").resolve()),
            defaults,
            "__session",
            version,
            command,
            *args,
        ],
        env,
    )
