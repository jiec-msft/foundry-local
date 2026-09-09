# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest

from ci import ROOT, RUNNERS, integration_command
from ci_prepare import verify


class BindingTests(unittest.TestCase):
    def arguments(self, **overrides):
        return argparse.Namespace(**({"java": Path("java"), "jar": Path("sdk.jar"),
            "runtime_dir": Path("runtime"), "cache_dir": Path("models"), "output": Path("results"),
            "target": "windows-arm64", "prepare": False, "accept_model_license": False} | overrides))

    def test_exact_runner_binding_and_no_implicit_download(self):
        command = integration_command(self.arguments())
        self.assertEqual(str(ROOT / "integration.py"), command[1])
        self.assertEqual(["--timeout-seconds", "840"], command[-2:])
        self.assertNotIn("--prepare", command)
        self.assertIn("--cache-dir", command)
        prepared = integration_command(self.arguments(prepare=True, accept_model_license=True))
        self.assertEqual(["--prepare", "--accept-model-license"], prepared[-2:])

    def test_download_license_flags_are_paired(self):
        for flags in ({"prepare": True}, {"accept_model_license": True}):
            with self.assertRaises(ValueError):
                integration_command(self.arguments(**flags))

    def test_pins_and_native_jdk_selection(self):
        lock = json.loads((ROOT / "ci-tools-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(set(RUNNERS), set(lock["jdk"]))
        for target, pin in lock["jdk"].items():
            self.assertEqual(17, pin["major"])
            self.assertRegex(pin["sha256"], r"^[0-9a-f]{64}$")
            prefix = ("https://download.visualstudio.microsoft.com/download/pr/" if target == "windows-arm64"
                      else "https://github.com/adoptium/temurin17-binaries/")
            self.assertTrue(pin["url"].startswith(prefix))
            self.assertGreater(pin["bytes"], 0)

    def test_mismatched_artifact_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "refusing substitution"):
            verify(ROOT / "ci-tools-lock.json", {"sha256": "0" * 64})

    def test_pending_refresh_blocks_integration_before_any_java_launch(self):
        command = [
            sys.executable, str(ROOT / "ci.py"), "integration", "--target", "windows-x64",
            "--java", "must-not-launch-java", "--jar", "not-a-jar", "--runtime-dir", "not-a-runtime",
            "--cache-dir", "not-a-cache", "--output", str(ROOT / "build" / "TestResults" / "must-not-run"),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("qualified SDK source-pin refresh", result.stderr)
        self.assertNotIn("FileNotFoundError", result.stderr)


if __name__ == "__main__":
    unittest.main()
