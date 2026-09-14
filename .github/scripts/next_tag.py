"""Select the next stable release tag without changing the repository."""

import re
import subprocess
from collections.abc import Iterable

RELEASE_PATHS = {"flake.nix", "flake.lock", "libexec", "nix", "skills", "LICENSE", "NOTICE.md"}


def stable_version(tag: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag)
    if match is None:
        return None
    return int(match[1]), int(match[2]), int(match[3])


def next_tag(tags: Iterable[str], head_tags: Iterable[str]) -> str | None:
    if any(stable_version(tag) is not None for tag in head_tags):
        return None
    versions = [version for tag in tags if (version := stable_version(tag)) is not None]
    if not versions:
        return "v0.1.0"
    major, minor, patch = max(versions)
    return f"v{major}.{minor}.{patch + 1}"


def latest_stable_tag(tags: Iterable[str]) -> str | None:
    return max(
        (tag for tag in tags if stable_version(tag) is not None),
        key=lambda tag: stable_version(tag) or (0, 0, 0),
        default=None,
    )


def release_plan(
    tags: Iterable[str], head_tags: Iterable[str], changed_paths: Iterable[str] | None
) -> tuple[str, bool]:
    if existing := latest_stable_tag(head_tags):
        return existing, False
    if changed_paths is not None and not any(
        path.split("/", 1)[0] in RELEASE_PATHS for path in changed_paths
    ):
        return "", False
    return next_tag(tags, []) or "", True


def main() -> None:
    tags = subprocess.check_output(["git", "tag", "--list"], text=True).splitlines()
    head_tags = subprocess.check_output(
        ["git", "tag", "--points-at", "HEAD"], text=True
    ).splitlines()
    baseline = latest_stable_tag(
        subprocess.check_output(["git", "tag", "--merged", "HEAD"], text=True).splitlines()
    )
    # Compare with the last reachable release, including changes from failed pushes.
    changed_paths = (
        subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", baseline, "HEAD", "--"],
            text=True,
        ).split("\0")
        if baseline
        else None
    )
    tag, create_tag = release_plan(tags, head_tags, changed_paths)
    print(f"tag={tag}")
    print(f"create_tag={str(create_tag).lower()}")


if __name__ == "__main__":
    main()
