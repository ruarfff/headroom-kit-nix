"""Nix entry point: import only the adjacent immutable Kit implementation."""

import signal
import subprocess
import sys
from pathlib import Path


def entrypoint() -> None:
    # Python -I excludes the script directory. Add only this trusted source root.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from kit_runtime import KitError, say, stop
    from kit_session import main

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    try:
        sys.exit(main())
    except KitError as error:
        say(str(error))
    except (OSError, subprocess.SubprocessError):
        say("A local process or file operation failed. Check paths, permissions, and disk space.")
    sys.exit(1)


if __name__ == "__main__":
    entrypoint()
