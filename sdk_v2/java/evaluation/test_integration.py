# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Offline contract checks only; these fixtures are not model evidence."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from integration import measured_sample, require_cleanup, unknown, verify_model
from model_inventory import METADATA_FILES, METADATA_SHA, validate_target_schema
from scorer import score_measurement
from test_scorer import synthetic_manifest, synthetic_measurement


def version_two():
    measurement = synthetic_measurement()
    measurement["schema_version"] = 2
    measurement["batch_samples"] = copy.deepcopy(measurement["samples"])
    for sample in measurement["batch_samples"]:
        sample["timing"]["mode"] = "batch"
    measurement["readiness"]["elapsed_ms"] = unknown("No end-to-end readiness clock")
    measurement["readiness"]["model_load_ms"] = [10, 20]
    measurement["resources"].update(
        model_download_bytes=unknown("Percentages only"),
        runtime_download_bytes=unknown("No transfer instrument"),
        artifact_download_bytes=unknown("Existing artifacts"),
        sdk_artifact_bytes=100,
    )
    measurement["cancellation"] = {
        "verified": True, "cancellation_requested_ms": 1200, "acknowledged_ms": 1250,
        "acknowledgment_latency_ms": 50, "natural_input_closed_ms": None, "submitted_bytes": 38400,
        "cleanup_verified": True,
    }
    measurement["provenance"] = {
        "sdk_jar_sha256": "a" * 64, "jna_sha256": "b" * 64, "native_sha256": {"native.dll": "c" * 64},
        "timing_origin": "request-local", "coverage": "synthetic unit data only",
    }
    return measurement


class IntegrationContractTests(unittest.TestCase):
    def test_model_mismatch_retains_actual_hashes_without_accepting_line_endings(self):
        build = Path(__file__).resolve().parent / "build" / "TestResults"
        build.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as directory:
            root = Path(directory)
            cache = root / "model"
            cache.mkdir()
            contents = {"genai_config.json": b"{}", "inference_model.json": b'{\r\n  "unit": true\r\n}'}
            contents.update({f"unit-{i:02}.bin": b"unit" for i in range(14)})
            files = []
            for name, data in contents.items():
                (cache / name).write_bytes(data)
                files.append({"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            manifest = "".join(f"{item['name']}\t{item['bytes']}\t{item['sha256']}\n" for item in files)
            lock = {"files": files, "manifestSha256": hashlib.sha256(manifest.encode()).hexdigest(),
                    "installedBytes": sum(map(len, contents.values()))}
            evidence = root / "model-verification.json"
            self.assertEqual(sum(map(len, contents.values())), verify_model(cache, lock, evidence))
            self.assertEqual("matched", json.loads(evidence.read_text())["status"])
            changed = contents["inference_model.json"].replace(b"\r\n", b"\n")
            (cache / "inference_model.json").write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "Pinned model hash/size mismatch: inference_model.json"):
                verify_model(cache, lock, evidence)
            recorded = json.loads(evidence.read_text())
            self.assertEqual("mismatch", recorded["status"])
            self.assertEqual(hashlib.sha256(changed).hexdigest(), recorded["files"][1]["actual_sha256"])
            self.assertEqual(len(changed), recorded["files"][1]["actual_bytes"])
            self.assertTrue(recorded["files"][0]["matched"])
            self.assertNotEqual(recorded["expected_manifest_sha256"], recorded["actual_manifest_sha256"])
            (cache / "inference_model.json").write_bytes(contents["inference_model.json"])
            lock["manifestSha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "Model manifest hash mismatch"):
                verify_model(cache, lock, evidence)

    def test_unknown_measurements_preserve_reason_without_inventing_zero(self):
        measured = version_two()
        report = score_measurement(synthetic_manifest(), measured)
        self.assertEqual({"value": None, "reason": "Percentages only"},
                         report["measurement_raw"]["resources"]["model_download_bytes"])
        self.assertEqual(0, report["batch"]["corpus"]["errors"])
        measured["resources"]["model_download_bytes"]["reason"] = ""
        with self.assertRaises(ValueError):
            score_measurement(synthetic_manifest(), measured)

    def test_unknown_object_cannot_hide_an_invented_value(self):
        measured = version_two()
        measured["resources"]["model_download_bytes"]["value"] = 793344452
        with self.assertRaises(ValueError):
            score_measurement(synthetic_manifest(), measured)

    def test_v3_metadata_provenance_matches_actual_model_target_and_totals(self):
        measured = version_two()
        schema = json.loads((Path(__file__).resolve().parent / "measurement.schema.json").read_text())
        validate_target_schema(measured, schema)
        measured["schema_version"] = 3
        measured["sdk"]["metadata_git_sha"] = METADATA_SHA
        inventory = {
            "native_rid": "win-x64", "manifest_sha256": measured["model"]["sha256"],
            "installed_bytes": measured["resources"]["model_install_bytes"],
            "files_sha256": {name: "d" * 64 for name in METADATA_FILES},
        }
        measured["provenance"]["model_inventory"] = inventory
        validate_target_schema(measured, schema)
        report = score_measurement(synthetic_manifest(), measured)
        self.assertEqual(METADATA_SHA, report["measurement_raw"]["sdk"]["metadata_git_sha"])
        for key, value in (("native_rid", "windows-x64"), ("native_rid", "linux-x64"),
                           ("manifest_sha256", "f" * 64), ("installed_bytes", 201), ("files_sha256", {})):
            changed = copy.deepcopy(measured)
            changed["provenance"]["model_inventory"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                score_measurement(synthetic_manifest(), changed)
        del measured["sdk"]["metadata_git_sha"]
        with self.assertRaises(ValueError):
            score_measurement(synthetic_manifest(), measured)
        with self.assertRaisesRegex(ValueError, "JSON Schema"):
            validate_target_schema(measured, schema)

    def test_result_does_not_imply_cleanup(self):
        run = {"command": "unit", "events": [{"event": "result", "processChildren": 0}]}
        with self.assertRaises(ValueError):
            require_cleanup(run)
        run["events"] += [{"event": name} for name in ("requestClosed", "modelUnloaded", "managerClosed")]
        require_cleanup(run)
        run["events"][1], run["events"][2] = run["events"][2], run["events"][1]
        with self.assertRaises(ValueError):
            require_cleanup(run)

    def test_cancellation_is_not_natural_input_close(self):
        reference = {"id": "unit", "frames": 64000, "duration_seconds": 4}
        result = {
            "event": "result", "processChildren": 0, "audioSeconds": 4,
            "result": {"cancelled": True, "text": ""},
            "timing": {"cancellationRequestedMillis": 1200, "finalizedMillis": 1250,
                       "inputClosedMillis": None, "submittedBytes": 38400},
        }
        run = {"command": "unit", "events": [result] + [
            {"event": name} for name in ("requestClosed", "modelUnloaded", "managerClosed")]}
        self.assertEqual(50, measured_sample(reference, run, cancelled=True)["acknowledgment_latency_ms"])
        result["timing"]["inputClosedMillis"] = 4000
        with self.assertRaises(ValueError):
            measured_sample(reference, run, cancelled=True)


if __name__ == "__main__":
    unittest.main()
