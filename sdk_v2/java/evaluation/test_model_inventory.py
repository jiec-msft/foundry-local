# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Offline target-lock consumers; all cache bytes here are synthetic unit fixtures."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ci_prepare
import integration
import model_inventory
from model_inventory import METADATA_FILES, METADATA_SHA, SDK, SDK_SHA, ModelMetadata, load_model_metadata

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "TestResults"


def inventory_tuple(files):
    lines = "".join(f"{item['name']}\t{item['bytes']}\t{item['sha256']}\n"
                    for item in sorted(files, key=lambda item: item["name"]))
    return sum(item["bytes"] for item in files), hashlib.sha256(lines.encode()).hexdigest()


class MetadataConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BUILD.mkdir(parents=True, exist_ok=True)
        cls.contract = json.loads((ROOT / "sdk-contract.json").read_text())
        cls.metadata = load_model_metadata(cls.contract)
        cls.schema = json.loads(subprocess.check_output([
            "git", "show", f"{METADATA_SHA}:sdk_v2/java/model-target-lock.schema.json"
        ], cwd=SDK.parents[1]))

    def synthetic(self):
        base, targets = copy.deepcopy((self.metadata.base, self.metadata.targets))
        contents = {item["name"]: (item["name"] + "\n").encode() for item in base["files"]}
        contents["inference_model.json"] = b'{\r\n  "synthetic": true\r\n}'
        for item in base["files"]:
            data = contents[item["name"]]
            item.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        base["installedBytes"], base["manifestSha256"] = inventory_tuple(base["files"])
        targets["baseManifestSha256"] = base["manifestSha256"]
        for rid, target in targets["targets"].items():
            if target["status"] == "unobserved":
                continue
            data = contents["inference_model.json"]
            if rid == "linux-x64":
                data = data.replace(b"\r\n", b"\n")
            marker = {"name": "inference_model.json", "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()}
            files = [marker if item["name"] == marker["name"] else item for item in base["files"]]
            target["generatedMarker"] = marker
            target["installedBytes"], target["manifestSha256"] = inventory_tuple(files)
        return ModelMetadata(base, targets, self.metadata.selector, self.metadata.file_hashes), contents

    def test_exact_reviewed_selections_and_git_blob_hashes(self):
        for rid in ("win-x64", "win-arm64", "linux-x64"):
            selected = self.metadata.select(rid)
            self.assertEqual(rid, selected["inventoryTarget"])
            self.assertEqual(16, len(selected["files"]))
            self.assertEqual(793344449 if rid == "linux-x64" else 793344452, selected["installedBytes"])
        for rid in ("linux-arm64", "osx-arm64", "windows-x64", "macos-arm64"):
            with self.subTest(rid=rid), self.assertRaises(ValueError):
                self.metadata.select(rid)
        for name in METADATA_FILES:
            raw = subprocess.check_output(["git", "show", f"{METADATA_SHA}:sdk_v2/java/{name}"],
                                          cwd=SDK.parents[1])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), self.metadata.file_hashes[name])

    def test_actual_schema_rejects_fields_the_selector_does_not_validate(self):
        targets = copy.deepcopy(self.metadata.targets)
        targets["targets"]["linux-x64"]["evidence"]["unreviewed"] = "must not be ignored"
        with self.assertRaisesRegex(ValueError, "JSON Schema"):
            model_inventory.validate_target_schema(targets, self.schema)
        targets = copy.deepcopy(self.metadata.targets)
        targets["targets"]["linux-arm64"]["generatedMarker"] = targets["targets"]["linux-x64"]["generatedMarker"]
        with self.assertRaisesRegex(ValueError, "JSON Schema"):
            model_inventory.validate_target_schema(targets, self.schema)

    def test_raw_target_bytes_and_all_file_mismatch_evidence(self):
        metadata, contents = self.synthetic()
        for rid in ("win-x64", "win-arm64", "linux-x64"):
            with self.subTest(rid=rid), tempfile.TemporaryDirectory(dir=BUILD) as directory:
                root = Path(directory)
                cache = root / "cache"
                cache.mkdir()
                selected = metadata.select(rid)
                for name, raw in contents.items():
                    if name == "inference_model.json" and rid == "linux-x64":
                        raw = raw.replace(b"\r\n", b"\n")
                    (cache / name).write_bytes(raw)
                evidence = root / "verification.json"
                installed = integration.verify_model(cache, selected, evidence, METADATA_SHA)
                self.assertEqual(selected["installedBytes"], installed)
                self.assertEqual(installed, metadata.provenance(selected, installed)["installed_bytes"])
                for name in ("inference_model.json", "vocab.txt"):
                    file = cache / name
                    original = file.read_bytes()
                    file.write_bytes(original + b"invalid")
                    with self.assertRaisesRegex(ValueError, "Pinned model hash/size mismatch"):
                        integration.verify_model(cache, selected, evidence, METADATA_SHA)
                    observed = json.loads(evidence.read_text())
                    self.assertEqual(16, len(observed["files"]))
                    self.assertEqual([name], [item["name"] for item in observed["files"] if not item["matched"]])
                    self.assertEqual(rid, observed["inventory_target"])
                    self.assertEqual(METADATA_SHA, observed["metadata_git_sha"])
                    self.assertEqual(installed + 7, observed["actual_installed_bytes"])
                    file.write_bytes(original)
                for field, value in (("manifestSha256", "0" * 64), ("installedBytes", installed + 1)):
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        integration.verify_model(cache, {**selected, field: value}, evidence, METADATA_SHA)
                with self.assertRaises(ValueError):
                    metadata.provenance(selected, installed + 1)

    def test_synthetic_observed_arm_entries_do_not_promote_checked_in_metadata(self):
        metadata, _ = self.synthetic()
        for rid in ("linux-arm64", "osx-arm64"):
            metadata.targets["targets"][rid] = copy.deepcopy(metadata.targets["targets"]["linux-x64"])
            self.assertEqual(rid, metadata.select(rid)["inventoryTarget"])
            with self.assertRaisesRegex(ValueError, "No reviewed observed"):
                self.metadata.select(rid)

    def test_unobserved_preparation_rejects_before_any_download(self):
        args = argparse.Namespace(target="linux-arm64")
        with patch("ci_prepare.host_identity", return_value=("linux", "arm64")), \
                patch("ci_prepare.load_model_metadata", return_value=self.metadata), \
                patch("ci_prepare.download") as download:
            with self.assertRaisesRegex(ValueError, "No reviewed observed"):
                ci_prepare.prepare(args)
            download.assert_not_called()

    def test_native_integration_selects_verified_rid_before_native_cli(self):
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            command = ["integration.py", "--java", "not-java", "--jar", "not-jar", "--runtime-dir", "not-runtime",
                       "--cache-dir", "not-cache", "--output", str(Path(directory) / "run"), "--target", "linux-arm64"]
            with patch.object(sys, "argv", command), \
                    patch("integration.load_model_metadata", return_value=self.metadata), \
                    patch("integration.verify_artifacts", return_value=({}, "linux-arm64", {})), \
                    patch("integration.run_cli") as launch:
                with self.assertRaisesRegex(ValueError, "No reviewed observed"):
                    integration.main()
                launch.assert_not_called()

    def test_wrong_metadata_revision_rejects_before_source_or_schema_execution(self):
        for pin in (None, SDK_SHA, "f" * 40):
            with self.subTest(pin=pin), patch("model_inventory.subprocess.run") as execute:
                with self.assertRaisesRegex(ValueError, "Metadata SHA"):
                    load_model_metadata({**self.contract, "metadata_git_sha": pin})
                execute.assert_not_called()


class SourceDriftTests(unittest.TestCase):
    def test_metadata_and_binary_drift_are_independently_rejected(self):
        BUILD.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=BUILD) as directory:
            root = Path(directory)
            sdk = root / "sdk_v2" / "java"
            (sdk / "scripts").mkdir(parents=True)

            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.STDOUT).decode().strip()

            git("init", "--quiet")
            git("config", "core.autocrlf", "false")
            (sdk / "pom.xml").write_text("<project/>\n")
            source = sdk / "src" / "main" / "java" / "Unit.java"
            source.parent.mkdir(parents=True)
            source.write_text("class Unit {}\n")
            (sdk / "model-lock.json").write_bytes((SDK / "model-lock.json").read_bytes())
            git("add", ".")
            message = "Synthetic source fixture\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
            git("-c", "user.name=Unit Test", "-c", "user.email=unit@example.invalid", "commit", "--quiet", "-m", message)
            binary_sha = git("rev-parse", "HEAD")
            for name in METADATA_FILES:
                (sdk / name).write_bytes(subprocess.check_output(
                    ["git", "show", f"{METADATA_SHA}:sdk_v2/java/{name}"], cwd=SDK.parents[1]))
            git("add", ".")
            git("-c", "user.name=Unit Test", "-c", "user.email=unit@example.invalid", "commit", "--quiet", "-m", message)
            metadata_sha = git("rev-parse", "HEAD")
            contract = {"sdk_git_sha": binary_sha, "metadata_git_sha": metadata_sha}
            with patch("model_inventory.SDK_SHA", binary_sha), patch("model_inventory.METADATA_SHA", metadata_sha):
                self.assertEqual("linux-x64", load_model_metadata(contract, sdk).select("linux-x64")["inventoryTarget"])
                for name in (*METADATA_FILES, "pom.xml", "src/main/java/Unit.java", "model-lock.json"):
                    file = sdk / name
                    original = file.read_bytes()
                    file.write_bytes(original + b"\nchanged")
                    with self.subTest(name=name), self.assertRaises(subprocess.CalledProcessError):
                        load_model_metadata(contract, sdk)
                    file.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
