# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Golden and rejection tests. Every measurement made here is synthetic unit data."""

import copy
import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path

from scorer import edit_counts, load_json, normalize, score_measurement, score_pair


ROOT = Path(__file__).resolve().parent


def synthetic_manifest():
    return {
        "schema_version": 1,
        "fixture_set_id": "synthetic-unit-only",
        "samples": [
            {"id": "short", "subset": "dev-clean", "reference_raw": "ONE", "duration_seconds": 4},
            {"id": "long", "subset": "dev-other", "reference_raw": "one two three four five six seven eight nine",
             "duration_seconds": 4},
        ],
    }


def synthetic_measurement(manifest=None):
    manifest = manifest or synthetic_manifest()
    samples = []
    for sample in manifest["samples"]:
        duration = sample["duration_seconds"] * 1000
        samples.append({
            "id": sample["id"],
            "hypothesis_raw": sample["reference_raw"],
            "timing": {
                "mode": "paced",
                "audio_duration_ms": duration,
                "feed_started_ms": 100,
                "first_nonempty_ms": 300,
                "input_closed_ms": 100 + duration,
                "finalized_ms": 300 + duration,
                "inference_wall_ms": 200 + duration,
                "chunk_duration_ms": 20,
            },
        })
    return {
        "schema_version": 1,
        "fixture_set_id": manifest["fixture_set_id"],
        "sdk": {"git_sha": "a" * 40},
        "environment": {
            "os": "windows", "host_arch": "x64", "jvm_arch": "x64", "native_arch": "x64",
            "jdk_version": "17.0.16+8", "jdk_vendor": "synthetic unit test",
        },
        "runtime": {"version": "synthetic-unit", "sha256": "b" * 64},
        "model": {"id": "synthetic-unit", "version": "unit", "sha256": "c" * 64},
        "readiness": {"status": "ready", "elapsed_ms": 200, "cold_start": False},
        "resources": {
            "peak_rss_bytes": 1000, "rss_method": "synthetic unit data, not observed RSS",
            "runtime_download_bytes": 0, "model_download_bytes": 0,
            "runtime_install_bytes": 100, "model_install_bytes": 200,
        },
        "lifecycle": {"native_loaded": True, "cancel_verified": True, "cleanup_verified": True},
        "samples": samples,
    }


class GoldenWerTests(unittest.TestCase):
    def test_hand_authored_golden_edit_counts(self):
        cases = [
            ("one two", "one two", (0, 0, 0, 2, 0)),
            ("one two", "one blue", (1, 0, 0, 2, 0.5)),
            ("one two three", "one three", (0, 1, 0, 3, 1 / 3)),
            ("one two", "one new two", (0, 0, 1, 2, 0.5)),
            ("one two three", "one blue three four", (1, 0, 1, 3, 2 / 3)),
            ("a b", "b a", (2, 0, 0, 2, 1)),
            ("a a", "a", (0, 1, 0, 2, 0.5)),
            ("a", "", (0, 1, 0, 1, 1)),
            ("", "a b", (0, 0, 2, 0, None)),
            ("", "", (0, 0, 0, 0, None)),
            ("a", "b c d", (1, 0, 2, 1, 3)),
        ]
        for reference, hypothesis, golden in cases:
            with self.subTest(reference=reference, hypothesis=hypothesis):
                score = score_pair(reference, hypothesis)
                self.assertEqual(golden, tuple(score[key] for key in (
                    "substitutions", "deletions", "insertions", "reference_words", "wer"
                )))
                self.assertEqual(score["errors"], sum(score[key] for key in ("substitutions", "deletions", "insertions")))

    def test_normalization_preserves_raw_and_numbers(self):
        raw = "\u2018DON\u2019T\u2019  re-enter\t\uFF11\uFF12 3.5 Stra\u00dfe, caf\u00e9!"
        self.assertEqual("don't re enter 12 3 5 strasse caf\u00e9", normalize(raw))
        score = score_pair(raw, "Don't re enter 12 3 5 STRASSE caf\u00e9")
        self.assertEqual(raw, score["reference_raw"])
        self.assertEqual(0, score["errors"])
        self.assertNotEqual(normalize("12"), normalize("twelve"))
        self.assertEqual("l'amour", normalize("L\u02bcAMOUR"))
        self.assertEqual("hello world", normalize("hello_world"))

    def test_exhaustive_small_distances_against_recursive_definition(self):
        @lru_cache(None)
        def distance(reference, hypothesis):
            if not reference:
                return len(hypothesis)
            if not hypothesis:
                return len(reference)
            return min(
                distance(reference[1:], hypothesis[1:]) + (reference[0] != hypothesis[0]),
                distance(reference[1:], hypothesis) + 1,
                distance(reference, hypothesis[1:]) + 1,
            )
        words = [tuple(value) for size in range(4) for value in itertools.product(("a", "b"), repeat=size)]
        for reference in words:
            for hypothesis in words:
                self.assertEqual(distance(reference, hypothesis), edit_counts(reference, hypothesis)["errors"])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = synthetic_manifest()
        self.measurement = synthetic_measurement()

    def test_pooled_wer_not_mean_and_clean_other_breakdown(self):
        self.measurement["samples"][0]["hypothesis_raw"] = "wrong"
        report = score_measurement(self.manifest, self.measurement)
        self.assertEqual(0.1, report["corpus"]["wer"])
        self.assertNotEqual(0.5, report["corpus"]["wer"])
        self.assertEqual(1, report["subsets"]["dev-clean"]["wer"])
        self.assertEqual(0, report["subsets"]["dev-other"]["wer"])
        self.assertEqual(10, report["corpus"]["reference_words"])

    def test_raw_evidence_is_preserved_and_not_aliased(self):
        report = score_measurement(self.manifest, self.measurement)
        self.assertEqual(self.measurement, report["measurement_raw"])
        self.measurement["samples"][0]["hypothesis_raw"] = "changed after scoring"
        self.assertEqual("ONE", report["measurement_raw"]["samples"][0]["hypothesis_raw"])
        self.assertEqual("ONE", report["samples"][0]["reference_raw"])
        self.assertEqual("one", report["samples"][0]["reference_normalized"])
        self.assertEqual(200, report["samples"][0]["first_nonempty_latency_ms"])
        self.assertEqual(200, report["samples"][0]["finalization_latency_ms"])
        self.assertEqual(1.05, report["samples"][0]["paced_rtf"])

    def test_empty_output_has_null_latency_and_deletions(self):
        self.measurement["samples"][0]["hypothesis_raw"] = ""
        self.measurement["samples"][0]["timing"]["first_nonempty_ms"] = None
        score = score_measurement(self.manifest, self.measurement)["samples"][0]
        self.assertIsNone(score["first_nonempty_latency_ms"])
        self.assertEqual(1, score["deletions"])

    def test_every_frozen_fixture_is_required_without_reordering_output(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        measurement = synthetic_measurement(manifest)
        measurement["samples"].reverse()
        report = score_measurement(manifest, measurement)
        self.assertEqual([sample["id"] for sample in manifest["samples"]], [sample["id"] for sample in report["samples"]])
        self.assertEqual(10, len(report["samples"]))
        self.assertEqual(0, report["corpus"]["errors"])

    def test_missing_duplicate_and_unknown_samples_rejected(self):
        for change in ("missing", "duplicate", "unknown"):
            measured = copy.deepcopy(self.measurement)
            if change == "missing":
                measured["samples"].pop()
            elif change == "duplicate":
                measured["samples"].append(copy.deepcopy(measured["samples"][0]))
            else:
                measured["samples"][0]["id"] = "unknown"
            with self.subTest(change=change), self.assertRaises(ValueError):
                score_measurement(self.manifest, measured)
        del self.measurement["samples"][0]["hypothesis_raw"]
        with self.assertRaises(ValueError):
            score_measurement(self.manifest, self.measurement)

    def test_nonfinite_negative_boolean_and_unknown_metrics_rejected(self):
        for value in (float("nan"), float("inf"), -1, True, "200"):
            measured = copy.deepcopy(self.measurement)
            measured["readiness"]["elapsed_ms"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                score_measurement(self.manifest, measured)
        self.measurement["resources"]["invented_metric"] = 0
        with self.assertRaises(ValueError):
            score_measurement(self.manifest, self.measurement)

    def test_timing_denominator_pacing_and_event_order_rejected(self):
        changes = [
            ("audio_duration_ms", 5000),
            ("inference_wall_ms", 1),
            ("input_closed_ms", 50),
            ("input_closed_ms", 200),
            ("finalized_ms", 300),
            ("first_nonempty_ms", 99),
            ("first_nonempty_ms", 100000),
            ("first_nonempty_ms", None),
            ("chunk_duration_ms", 0),
            ("chunk_duration_ms", 4000),
            ("mode", "batch"),
        ]
        for field, value in changes:
            measured = copy.deepcopy(self.measurement)
            measured["samples"][0]["timing"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                score_measurement(self.manifest, measured)

    def test_real_lifecycle_architectures_jdk_and_hashes_are_required(self):
        changes = [
            ("lifecycle", "native_loaded", False), ("lifecycle", "cancel_verified", False),
            ("lifecycle", "cleanup_verified", 1), ("environment", "native_arch", "arm64"),
            ("environment", "jvm_arch", "arm64"), ("environment", "jdk_version", "11"),
            ("environment", "os", "macos"), ("runtime", "sha256", "unpinned"),
            ("sdk", "git_sha", "main"), ("readiness", "status", "not_ready"),
            ("resources", "peak_rss_bytes", 0), ("resources", "runtime_download_bytes", 0.5),
        ]
        for section, field, value in changes:
            measured = copy.deepcopy(self.measurement)
            measured[section][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                score_measurement(self.manifest, measured)

    def test_manifest_errors_and_mismatched_set_rejected(self):
        self.measurement["fixture_set_id"] = "wrong"
        with self.assertRaises(ValueError):
            score_measurement(self.manifest, self.measurement)
        self.measurement = synthetic_measurement()
        self.manifest["samples"][0]["reference_raw"] = "!!!"
        with self.assertRaises(ValueError):
            score_measurement(self.manifest, self.measurement)


class CliTests(unittest.TestCase):
    def setUp(self):
        build = ROOT / "build" / "TestResults"
        build.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=build)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_cli_writes_report_and_preserves_raw_input(self):
        manifest, measurement, output = (self.root / name for name in ("manifest.json", "raw.json", "report.json"))
        manifest.write_text(json.dumps(synthetic_manifest()), encoding="utf-8")
        raw = json.dumps(synthetic_measurement())
        measurement.write_text(raw, encoding="utf-8")
        command = [sys.executable, str(ROOT / "scorer.py"), "--manifest", str(manifest),
                   "--measurement", str(measurement), "--output", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0, load_json(output)["corpus"]["errors"])
        self.assertEqual(raw, measurement.read_text(encoding="utf-8"))
        command[-1] = str(measurement)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(raw, measurement.read_text(encoding="utf-8"))

    def test_duplicate_json_keys_and_nonfinite_json_rejected(self):
        path = self.root / "invalid.json"
        for content in ('{"a":1,"a":2}', '{"metric":NaN}', '{"metric":Infinity}'):
            path.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
