"""Install once per wheel/Python pair, then run the released CLI without uv."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HEALTH_CHECK = """
import importlib.metadata as metadata
import importlib.util
import json
import os
import sys
from headroom_kit.runtime import installed_headroom_version
installed_headroom_version()
assert importlib.util.find_spec('headroom') is not None
print(json.dumps({
    'python': os.path.realpath(sys._base_executable),
    'packages': sorted((d.metadata['Name'], d.version) for d in metadata.distributions()),
}))
"""


def health(python: Path) -> dict | None:
    try:
        result = subprocess.run(
            [str(python), "-I", "-c", HEALTH_CHECK],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
        state = json.loads(result.stdout)
        if result.returncode == 0 and state["python"] == str(Path(sys.executable).resolve()):
            return state
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        pass
    return None


def cached_python(root: Path) -> Path | None:
    try:
        ready = json.loads((root / "ready.json").read_text())
        directory = ready["directory"]
        if not directory.startswith("env-") or Path(directory).name != directory:
            return None
        python = root / directory / "headroom-kit/bin/python"
        if health(python) == ready["health"] and ready["health"] is not None:
            return python
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def install(uv: str, wheel: str, directory: Path, lock: int) -> dict:
    print(
        "Headroom Kit: Installing the pinned CLI environment. Package-index access may be needed.",
        file=sys.stderr,
        flush=True,
    )
    env = {**os.environ, "UV_TOOL_DIR": str(directory), "UV_TOOL_BIN_DIR": str(directory / "bin")}
    # Tool commands ignore project config and retain user/system indexes and native auth.
    with subprocess.Popen(
        [
            uv,
            "tool",
            "install",
            "--no-python-downloads",
            "--python",
            sys.executable,
            "--prerelease",
            "disallow",
            "--link-mode",
            "copy",
            wheel,
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Keep the lock held if this launcher is killed while uv is still installing.
        pass_fds=(lock,),
    ) as process:
        try:
            while True:
                try:
                    code = process.wait(timeout=15)
                    break
                except subprocess.TimeoutExpired:
                    print(
                        "Headroom Kit: Setup is still running; waiting for index access and downloads.",
                        file=sys.stderr,
                        flush=True,
                    )
        except BaseException:
            process.kill()
            process.wait()
            raise
    state = health(directory / "headroom-kit/bin/python") if code == 0 else None
    if state is None:
        raise RuntimeError(
            "Cannot install or validate the pinned CLI environment. "
            "Check uv index access and authentication (including native Keychain), CA settings, "
            "and cache permissions. Resolver diagnostics are hidden to protect credentials. "
            "Setup was not published; the next launch will retry."
        )
    return state


def resolve(uv: str, wheel: str) -> str:
    identity = f"1\0{Path(wheel).resolve(strict=True)}\0{Path(sys.executable).resolve()}"
    key = hashlib.sha256(os.fsencode(identity)).hexdigest()
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache").resolve()
    root = cache / "headroom-kit/environments-v1" / key
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if python := cached_python(root):
        return str(python)
    with (root / "setup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                "Headroom Kit: Waiting for another launcher to finish setup.",
                file=sys.stderr,
                flush=True,
            )
            fcntl.flock(lock, fcntl.LOCK_EX)
        if python := cached_python(root):
            return str(python)
        # Remove abandoned setup only. Complete generations may still serve live proxies.
        for abandoned in root.glob("env-*"):
            if not (abandoned / "complete").exists():
                shutil.rmtree(abandoned)
        directory = Path(tempfile.mkdtemp(prefix="env-", dir=root))
        try:
            state = install(uv, wheel, directory, lock.fileno())
            (directory / "complete").touch()
            ready = root / "ready.next"
            ready.write_text(json.dumps({"directory": directory.name, "health": state}))
            ready.replace(root / "ready.json")
        except BaseException:
            shutil.rmtree(directory)
            raise
        print("Headroom Kit: CLI environment is ready.", file=sys.stderr, flush=True)
        return str(directory / "headroom-kit/bin/python")


def main() -> None:
    uv, wheel, defaults, command, *args = sys.argv[1:]
    if command == "headroom-kit":
        # Explicit --config files replace Nix defaults. --version must stand alone.
        if args[:1] == ["run"]:
            args = ["--config", defaults, *args]
    elif command != "headroom":
        agent = command.removesuffix("-headroom")
        args = ["--config", defaults, "run", agent, "--", *args]
    python = resolve(uv, wheel)
    module = "headroom.cli" if command == "headroom" else "headroom_kit"
    os.execv(python, [python, "-I", "-m", module, *args])


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError):
        sys.exit(
            "Headroom Kit: A local process or file operation failed. Check paths and permissions."
        )
    except RuntimeError as error:
        sys.exit(f"Headroom Kit: {error}")
    except KeyboardInterrupt:
        sys.exit(130)
