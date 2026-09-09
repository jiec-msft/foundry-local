# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Offline contract checks only; these fixtures are not model evidence."""

import copy
import unittest

from integration import measured_sample, require_cleanup, unknown
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
