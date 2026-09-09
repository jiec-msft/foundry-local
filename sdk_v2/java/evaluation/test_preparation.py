# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import hashlib
import json
import struct
import tempfile
import unittest
import wave
import zipfile
from collections import Counter
from pathlib import Path

from ci import previous_full_count, validate_dispatch
from model_inventory import METADATA_SHA
from platform_checks import assert_identities, assert_supported, native_identity, normalize_arch
from prepare_fixtures import flac_streaminfo
from stage_artifacts import stage, stage_failure


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "TestResults"


class FixtureTests(unittest.TestCase):
    def test_committed_public_smoke_contract_and_hashes(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        samples = manifest["samples"]
        self.assertEqual(10, len(samples))
        self.assertEqual(Counter({"dev-clean": 5, "dev-other": 5}), Counter(s["subset"] for s in samples))
        self.assertEqual(10, len({s["speaker_id"] for s in samples}))
        self.assertEqual(10, len({s["id"] for s in samples}))
        self.assertEqual("CC-BY-4.0", manifest["license"])
        for sample in samples:
            with self.subTest(id=sample["id"]):
                path = ROOT / sample["wav_path"]
                self.assertTrue(path.resolve().is_relative_to(ROOT / "fixtures"))
                self.assertTrue(sample["reference_raw"].strip())
                self.assertEqual(sample["wav_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(sample["wav_bytes"], path.stat().st_size)
                with wave.open(str(path), "rb") as wav:
                    self.assertEqual((1, 2, 16000, "NONE"), (
                        wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()
                    ))
                    self.assertEqual(sample["frames"], wav.getnframes())
                    duration = wav.getnframes() / wav.getframerate()
                    self.assertEqual(sample["duration_seconds"], duration)
                    self.assertGreaterEqual(duration, 4)
                    self.assertLessEqual(duration, 10)
                    pcm = wav.readframes(wav.getnframes())
                    self.assertEqual(sample["pcm_sha256"], hashlib.sha256(pcm).hexdigest())
                    self.assertEqual(wav.getnframes() * 2, len(pcm))
                self.assertEqual(44 + len(pcm), sample["wav_bytes"])

    def test_streaminfo_reads_exact_format_and_frame_count(self):
        packed = (16000 << 44) | (15 << 36) | 108800
        header = b"fLaC\x00\x00\x00\x22" + bytes(10) + packed.to_bytes(8, "big") + bytes(16)
        self.assertEqual({"sample_rate": 16000, "channels": 1, "bits_per_sample": 16, "frames": 108800},
                         flac_streaminfo(header))
        with self.assertRaises(ValueError):
            flac_streaminfo(b"not FLAC")
        with self.assertRaises(ValueError):
            flac_streaminfo(b"fLaC")


class PlatformTests(unittest.TestCase):
    def setUp(self):
        BUILD.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=BUILD)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def binary(self, data):
        path = self.root / "native.bin"
        path.write_bytes(data)
        return path

    def test_arch_aliases(self):
        self.assertEqual("x64", normalize_arch("AMD64"))
        self.assertEqual("arm64", normalize_arch("aarch64"))
        with self.assertRaises(ValueError):
            normalize_arch("x86")

    def test_macos_x64_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError, "Unsupported.*macos-x64"):
            assert_supported("macos", "x64")
        macho = b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x01000007)
        with self.assertRaisesRegex(ValueError, "Unsupported.*macos-x64"):
            native_identity(self.binary(macho))

    def test_pe_elf_and_macho_machine_architectures(self):
        pe = bytearray(64)
        pe[:2] = b"MZ"
        struct.pack_into("<I", pe, 60, 64)
        self.assertEqual(("windows", "arm64"), native_identity(self.binary(pe + b"PE\0\0\x64\xaa")))
        elf = bytearray(64)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 62)
        self.assertEqual(("linux", "x64"), native_identity(self.binary(elf)))
        macho = b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C)
        self.assertEqual(("macos", "arm64"), native_identity(self.binary(macho)))

    def test_no_universal_or_mismatched_architecture(self):
        with self.assertRaises(ValueError):
            native_identity(self.binary(b"\xca\xfe\xba\xbe" + bytes(20)))
        host = ("windows", "arm64")
        assert_identities("windows", "arm64", host, "arm64", [host, host])
        for observed_host, jvm, natives in [(("windows", "x64"), "arm64", [host]),
                                            (host, "x64", [host]), (host, "arm64", [("windows", "x64")]),
                                            (host, "arm64", [])]:
            with self.assertRaises(ValueError):
                assert_identities("windows", "arm64", observed_host, jvm, natives)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "ci-lock.json").read_text(encoding="utf-8"))
        self.contract = json.loads((ROOT / "sdk-contract.json").read_text(encoding="utf-8"))
        self.context = {
            "repository": "jiec-msft/foundry-local", "actor": "jiec-msft",
            "ref": "refs/heads/mason/java-asr-evaluation", "run_attempt": 1,
            "sdk_sha": "a" * 40, "lane": "full-matrix", "fix_sha": "", "fix_reason": "",
        }

    def ready_synthetic_unit_lock(self):
        for key in ("enabled", "dispatch_authorized", "integration_adapter_ready", "dependency_license_review_complete"):
            self.lock[key] = True
        self.lock["source_pin_refresh_required"] = False
        self.lock["sdk_git_sha"] = self.contract["sdk_git_sha"] = self.context["sdk_sha"]
        self.lock["local_windows_evidence"] = {"sdk_git_sha": "a" * 40, "sha256": "b" * 64}
        self.lock["model"] = {"sha256": "c" * 64}
        for dependency in self.contract["runtime"]["dependencies"]:
            dependency["sha256"] = "d" * 64

    def test_each_authorization_gate_rejects_when_false(self):
        self.ready_synthetic_unit_lock()
        for gate in ("enabled", "dispatch_authorized", "integration_adapter_ready", "dependency_license_review_complete"):
            with self.subTest(gate=gate), self.assertRaisesRegex(ValueError, "BLOCKED"):
                validate_dispatch({**self.lock, gate: False}, self.contract, self.context, 0)

    def test_checked_in_readiness_lock_is_coherent(self):
        sdk_sha = "d0946a0764d9cfa4b3d684940d6d5c66165427b8"
        for gate in ("enabled", "integration_adapter_ready", "dependency_license_review_complete"):
            self.assertIs(self.lock[gate], True)
        self.assertIs(self.lock["dispatch_authorized"], False)
        self.assertEqual(METADATA_SHA, self.lock["metadata_git_sha"])
        self.assertEqual(METADATA_SHA, self.contract["metadata_git_sha"])
        self.assertIs(self.lock["source_pin_refresh_required"], False)
        self.assertEqual(sdk_sha, self.contract["sdk_git_sha"])
        self.assertEqual(sdk_sha, self.lock["sdk_git_sha"])
        self.assertEqual(sdk_sha, self.lock["local_windows_evidence"]["sdk_git_sha"])
        self.assertEqual(64000, self.contract["sdk_jar"]["bytes"])
        self.assertEqual(self.contract["sdk_jar"]["sha256"],
                         self.lock["local_windows_evidence"]["canonical_rebuild"]["sha256"])
        model = json.loads((ROOT.parent / "model-lock.json").read_text(encoding="utf-8"))
        self.assertEqual(model["id"], self.lock["model"]["id"])
        self.assertEqual(model["manifestSha256"], self.lock["model"]["sha256"])
        self.assertIs(self.lock["model"]["redistribution_authorized"], False)
        self.assertEqual({target["id"] for target in self.contract["supported_targets"]},
                         set(self.lock["ci_lane_status"]))
        self.assertEqual({"not_run"}, set(self.lock["ci_lane_status"].values()))
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            validate_dispatch(self.lock, self.contract, {**self.context, "sdk_sha": sdk_sha}, 0)
        workflows = ROOT.parents[2] / ".github" / "workflows"
        self.assertEqual(["java-sdk-evaluation.yml"], sorted(p.name for p in workflows.glob("java-sdk*.yml")))

    def test_model_evidence_dependency_and_resource_guards_reject(self):
        self.ready_synthetic_unit_lock()
        for field, value in (("model", None), ("model", {"sha256": "unpinned"}),
                             ("local_windows_evidence", None), ("maximum_full_matrices", 3),
                             ("max_parallel", 3), ("job_timeout_minutes", 21), ("cache_enabled", True)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_dispatch({**self.lock, field: value}, self.contract, self.context, 0)
        self.contract["runtime"]["dependencies"][0]["sha256"] = None
        with self.assertRaisesRegex(ValueError, "dependency hash"):
            validate_dispatch(self.lock, self.contract, self.context, 0)

    def test_stale_source_cannot_dispatch_even_with_other_authorizations(self):
        self.ready_synthetic_unit_lock()
        self.lock["source_pin_refresh_required"] = True
        with self.assertRaisesRegex(ValueError, "source-pin refresh"):
            validate_dispatch(self.lock, self.contract, self.context, 0)
        del self.lock["source_pin_refresh_required"]
        with self.assertRaisesRegex(ValueError, "source-pin refresh"):
            validate_dispatch(self.lock, self.contract, self.context, 0)

    def test_separate_metadata_pin_and_exact_native_rid_are_required(self):
        self.ready_synthetic_unit_lock()
        with self.assertRaisesRegex(ValueError, "Metadata SHA"):
            validate_dispatch({**self.lock, "metadata_git_sha": "f" * 40},
                              self.contract, self.context, 0)
        self.contract["supported_targets"][0]["rid"] = "windows-x64"
        with self.assertRaisesRegex(ValueError, "native RID"):
            validate_dispatch(self.lock, self.contract, self.context, 0)

    def test_all_five_standard_targets_only(self):
        self.ready_synthetic_unit_lock()
        matrix = validate_dispatch(self.lock, self.contract, self.context, 0)
        self.assertEqual(["windows-2022", "windows-11-arm", "ubuntu-24.04", "ubuntu-24.04-arm", "macos-15"],
                         [lane["runner"] for lane in matrix])
        self.assertEqual(["x64", "arm64", "x64", "arm64", "arm64"], [lane["arch"] for lane in matrix])

    def test_two_matrix_limit_and_no_whole_run_retry(self):
        self.ready_synthetic_unit_lock()
        validate_dispatch(self.lock, self.contract, self.context, 1)
        with self.assertRaisesRegex(ValueError, "Two full"):
            validate_dispatch(self.lock, self.contract, self.context, 2)
        self.context["run_attempt"] = 2
        with self.assertRaisesRegex(ValueError, "Do not rerun"):
            validate_dispatch(self.lock, self.contract, self.context, 0)

    def test_owner_ref_sdk_and_failed_lane_fix_guards(self):
        self.ready_synthetic_unit_lock()
        for key, value in [("repository", "other/repo"), ("actor", "someone"),
                           ("ref", "refs/heads/other"), ("sdk_sha", "e" * 40)]:
            context = {**self.context, key: value}
            with self.assertRaises(ValueError):
                validate_dispatch(self.lock, self.contract, context, 0)
        self.context["lane"] = "linux-arm64"
        with self.assertRaisesRegex(ValueError, "concrete fix"):
            validate_dispatch(self.lock, self.contract, self.context, 2)
        self.context.update(fix_sha="f" * 40, fix_reason="Synthetic unit-only fix description")
        self.assertEqual(1, len(validate_dispatch(self.lock, self.contract, self.context, 2)))

    def test_history_counts_failures_and_cancellations_conservatively(self):
        pages = [{"workflow_runs": [
            {"id": 1, "display_title": "Java ASR full-matrix a"},
            {"id": 2, "display_title": "Java ASR windows-x64 a"},
            {"id": 3, "display_title": "Java ASR full-matrix b"},
        ]}, {"workflow_runs": [{"id": 1, "display_title": "Java ASR full-matrix a"}]}]
        self.assertEqual(1, previous_full_count(pages, 3))
        self.assertEqual(2, previous_full_count(pages, 4))


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        BUILD.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=BUILD)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in ("measurement.json", "report.json"):
            (self.source / name).write_text('{"synthetic_unit_test":true}', encoding="utf-8")

    def test_only_allowlisted_evidence_and_checksums(self):
        (self.source / "model.onnx").write_bytes(bytes(32))
        output = self.root / "output"
        total = stage(self.source, output)
        self.assertEqual({"measurement.json", "report.json", "SHA256SUMS.json"},
                         {path.name for path in output.iterdir()})
        self.assertEqual(total, sum(path.stat().st_size for path in output.iterdir()))

    def test_budget_missing_evidence_and_bundled_natives_fail(self):
        with self.assertRaisesRegex(ValueError, "budget"):
            stage(self.source, self.root / "too-small", 1)
        with zipfile.ZipFile(self.source / "sdk.jar", "w") as jar:
            jar.writestr("native/foundry_local.dll", b"synthetic unit test")
        with self.assertRaisesRegex(ValueError, "must not contain"):
            stage(self.source, self.root / "bundled")
        (self.source / "report.json").unlink()
        with self.assertRaisesRegex(ValueError, "required"):
            stage(self.source, self.root / "missing")

    def test_public_urls_allowed_but_machine_paths_rejected(self):
        (self.source / "report.json").write_text('{"source":"https://www.openslr.org/12"}', encoding="utf-8")
        stage(self.source, self.root / "public")
        (self.source / "report.json").write_text('{"path":"C:\\\\Users\\\\example"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Machine-specific"):
            stage(self.source, self.root / "machine")

    def test_missing_native_run_is_incomplete_not_successful(self):
        destination = self.root / "failure"
        stage_failure(self.root / "no-run", destination)
        failure = json.loads((destination / "failure.json").read_text())
        self.assertEqual("incomplete", failure["status"])
        self.assertFalse(failure["measurement_retained_locally"])
        self.assertEqual([], failure["processes"])

    def test_failure_retains_only_model_integrity_metadata(self):
        metadata = {
            "status": "mismatch", "expected_manifest_sha256": "a" * 64, "actual_manifest_sha256": "b" * 64,
            "metadata_git_sha": METADATA_SHA, "inventory_target": "linux-x64",
            "expected_installed_bytes": 90, "actual_installed_bytes": 87,
            "raw_error": "C:\\Users\\example\\model",
            "files": [{
                "name": "inference_model.json", "expected_bytes": 90, "actual_bytes": 87,
                "expected_sha256": "c" * 64, "actual_sha256": "d" * 64, "matched": False,
                "contents": "Never export model contents",
            }],
        }
        (self.source / "model-verification.json").write_text(json.dumps(metadata), encoding="utf-8")
        destination = self.root / "model-failure"
        stage_failure(self.source, destination)
        failure = json.loads((destination / "failure.json").read_text())
        self.assertEqual("incomplete", failure["status"])
        recorded = failure["model_verification"]
        self.assertEqual("d" * 64, recorded["files"][0]["actual_sha256"])
        self.assertEqual(METADATA_SHA, recorded["metadata_git_sha"])
        self.assertEqual("linux-x64", recorded["inventory_target"])
        self.assertEqual(87, recorded["actual_installed_bytes"])
        self.assertNotIn("raw_error", recorded)
        self.assertNotIn("contents", recorded["files"][0])
        metadata["files"][0]["name"] = "C:\\Users\\example\\model"
        (self.source / "model-verification.json").write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "privacy"):
            stage_failure(self.source, self.root / "unsafe-failure")


if __name__ == "__main__":
    unittest.main()
