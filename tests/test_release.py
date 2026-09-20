"""Check release numbering without creating commits, tags, or remote writes."""

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github/scripts"))
release = importlib.import_module("next_tag")
next_tag = release.next_tag


class ReleaseTest(unittest.TestCase):
    def test_release_numbering_and_reruns(self) -> None:
        cases = [
            ([], [], "v0.1.0"),
            (["v0.1.0"], [], "v0.1.1"),
            (["v0.1.9", "v0.1.10", "v0.1.2"], [], "v0.1.11"),
            (["v1.9.9", "v2.0.0"], [], "v2.0.1"),
            (["notes", "v9.0.0-rc.1", "v8.0.0+build", "v01.2.3"], [], "v0.1.0"),
            (["v0.1.0", "v9.0.0-rc.1"], ["preview"], "v0.1.1"),
            (["v0.1.0"], ["v0.1.0"], None),
            (["v0.1.0", "v0.1.1"], ["preview", "v0.1.0"], None),
        ]
        for tags, head_tags, expected in cases:
            with self.subTest(tags=tags, head_tags=head_tags):
                self.assertEqual(next_tag(tags, head_tags), expected)

    def test_release_plan_recovers_after_tag_creation(self) -> None:
        self.assertEqual(release.release_plan([], [], None), ("v0.1.0", True))
        self.assertEqual(
            release.release_plan(["v0.1.0"], ["preview", "v0.1.0"], []),
            ("v0.1.0", False),
        )
        self.assertEqual(
            release.release_plan(["v1.0.0", "v2.0.0"], ["v1.0.0", "v2.0.0"], []),
            ("v2.0.0", False),
        )

    def test_release_plan_filters_changes(self) -> None:
        for path in (
            "flake.nix",
            "flake.lock",
            "libexec/kit_session.py",
            "nix/packages.nix",
        ):
            with self.subTest(path=path):
                self.assertEqual(release.release_plan(["v0.1.0"], [], [path]), ("v0.1.1", True))
        for paths in (
            [],
            [
                "README.md",
                "docs/usage.md",
                "tests/test_release.py",
                ".github/workflows/tag.yml",
                ".gitignore",
                "skills/install-headroom-kit/SKILL.md",
                "LICENSE",
                "NOTICE.md",
            ],
        ):
            with self.subTest(paths=paths):
                self.assertEqual(release.release_plan(["v0.1.0"], [], paths), ("", False))

    def test_cli_compares_with_the_last_reachable_release(self) -> None:
        cases = (
            (
                {"tag --list": "", "tag --points-at HEAD": "", "tag --merged HEAD": ""},
                "v0.1.0",
                True,
            ),
            (
                {
                    "tag --list": "v0.1.0\nv9.0.0",
                    "tag --points-at HEAD": "",
                    "tag --merged HEAD": "v0.1.0\npreview",
                    "diff --name-only --no-renames -z v0.1.0 HEAD --": "libexec/launch.py\0README.md\0",
                },
                "v9.0.1",
                True,
            ),
            (
                {
                    "tag --list": "v0.1.0",
                    "tag --points-at HEAD": "",
                    "tag --merged HEAD": "v0.1.0",
                    "diff --name-only --no-renames -z v0.1.0 HEAD --": "README.md\0docs/usage.md\0",
                },
                "",
                False,
            ),
            (
                {
                    "tag --list": "v0.1.0",
                    "tag --points-at HEAD": "v0.1.0",
                    "tag --merged HEAD": "v0.1.0",
                    "diff --name-only --no-renames -z v0.1.0 HEAD --": "",
                },
                "v0.1.0",
                False,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git = root / "git"
            git.write_text(
                f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
                "sys.stdout.write(json.loads(Path(__file__).with_name('responses.json').read_text())"
                "[' '.join(sys.argv[1:])])\n"
            )
            git.chmod(0o700)
            for responses, tag, create_tag in cases:
                with self.subTest(tag=tag, create_tag=create_tag):
                    (root / "responses.json").write_text(json.dumps(responses))
                    result = subprocess.run(
                        [sys.executable, str(Path(release.__file__).resolve())],
                        cwd=root,
                        env={"PATH": str(root), "HOME": str(root)},
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=True,
                    )
                    self.assertEqual(
                        result.stdout, f"tag={tag}\ncreate_tag={str(create_tag).lower()}\n"
                    )


if __name__ == "__main__":
    unittest.main()
