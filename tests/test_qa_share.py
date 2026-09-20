"""Classify live share QA without launching agents or GUI apps."""

import os
import subprocess
import unittest

import qa_share


def result(code: int, stderr: str, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, stdout, stderr)


class QaShareTests(unittest.TestCase):
    def test_missing_tools_lists_clis_only(self) -> None:
        previous = os.environ["PATH"]
        os.environ["PATH"] = "/nonexistent"
        try:
            missing = qa_share.missing_tools()
        finally:
            os.environ["PATH"] = previous
        self.assertEqual(
            {name for name in missing if name != "python3.13"},
            {"codex", "copilot", "pi", "opencode", "uvx"},
        )

    def test_provider_quota_markers(self) -> None:
        self.assertTrue(qa_share.provider_quota("insufficient_quota"))
        self.assertTrue(qa_share.provider_quota("Rate limit reached"))
        self.assertTrue(qa_share.provider_quota("HTTP 429 too many requests"))
        self.assertFalse(qa_share.provider_quota("Started Headroom 0.37.0 on port 1"))

    def test_quota_after_share_is_not_a_kit_failure(self) -> None:
        first = result(1, "Started Headroom 0.37.0 on port 1.\ninsufficient_quota\n")
        second = result(1, "Reusing Headroom 0.37.0 on port 1.\nRate limit reached\n")
        self.assertIsNone(qa_share.share_error("pi", first, second))
        self.assertTrue(qa_share.client_ok(first))

    def test_missing_start_or_reuse_is_a_kit_failure(self) -> None:
        first = result(1, "agent crashed before proxy\n")
        self.assertIn("first launch failed", qa_share.share_error("codex", first))
        started = result(0, "Started Headroom 0.37.0 on port 1.\n")
        reused_badly = result(1, "Started Headroom 0.37.0 on port 2.\n")
        self.assertIn("did not reuse", qa_share.share_error("codex", started, reused_badly))

    def test_non_quota_client_error_after_share_still_fails(self) -> None:
        first = result(0, "Started Headroom 0.37.0 on port 1.\n")
        second = result(1, "Reusing Headroom 0.37.0 on port 1.\nmodel not found\n")
        self.assertIn(
            "client failed after proxy share", qa_share.share_error("copilot", first, second)
        )
