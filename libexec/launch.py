"""Resolve the pinned CLI environment, then hand control to the released package."""

import os
import subprocess
import sys
from pathlib import Path


def resolve(uv: str, wheel: str) -> str:
    result = subprocess.run(
        [
            uv,
            "--no-env-file",
            "--isolated",
            "--no-python-downloads",
            "--python",
            sys.executable,
            "--prerelease",
            "disallow",
            "--from",
            wheel,
            "python",
            "-I",
            "-c",
            "import sys; print(sys.executable)",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        # Package-index diagnostics can contain credentials.
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    python = result.stdout.strip()
    if result.returncode or not Path(python).is_absolute() or not os.access(python, os.X_OK):
        raise RuntimeError(
            "Cannot install the pinned Headroom Kit CLI with Nix Python 3.13. "
            "Check network access, uv package indexes, cache permissions, and CA settings."
        )
    return python


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
