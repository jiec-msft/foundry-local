# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Independent deterministic WER scoring and strict measured-evidence validation.

Normalization v1: Unicode NFKC then casefold; letters/numbers/combining marks
survive; ASCII/curly/modifier apostrophes become ASCII apostrophes only between
alphanumeric characters; every other character becomes a word boundary.
Whitespace collapses. No number expansion, filler removal or spelling rewriting.
Levenshtein ties prefer match, then substitution, deletion, insertion locally.
Corpus WER is pooled edits / pooled reference words, never mean utterance WER.
"""

import argparse
import copy
import json
import math
import re
import unicodedata
from pathlib import Path

from platform_checks import assert_supported


NORMALIZATION_VERSION = "nfkc-casefold-internal-apostrophe-v1"
APOSTROPHES = {"'", "\u2018", "\u2019", "\u02bc"}
SUBSETS = ("dev-clean", "dev-other")


def normalize(text):
    if not isinstance(text, str):
        raise ValueError("Transcript must be a string")
    text = unicodedata.normalize("NFKC", text).casefold()
    output = []
    for index, character in enumerate(text):
        if character in APOSTROPHES:
            internal = 0 < index < len(text) - 1 and text[index - 1].isalnum() and text[index + 1].isalnum()
            output.append("'" if internal else " ")
        elif character.isalnum() or unicodedata.category(character).startswith("M"):
            output.append(character)
        else:
            output.append(" ")
    return " ".join("".join(output).split())


def edit_counts(reference_words, hypothesis_words):
    """Count a deterministic minimum-cost alignment using two DP rows."""
    previous = [(j, 0, 0, j) for j in range(len(hypothesis_words) + 1)]
    for i, reference in enumerate(reference_words, 1):
        current = [(i, 0, i, 0)]
        for j, hypothesis in enumerate(hypothesis_words, 1):
            diagonal = previous[j - 1]
            if reference == hypothesis:
                current.append(diagonal)
                continue
            deletion, insertion = previous[j], current[j - 1]
            candidates = [
                (diagonal[0] + 1, 0, diagonal[1] + 1, diagonal[2], diagonal[3]),
                (deletion[0] + 1, 1, deletion[1], deletion[2] + 1, deletion[3]),
                (insertion[0] + 1, 2, insertion[1], insertion[2], insertion[3] + 1),
            ]
            cost, _, substitutions, deletions, insertions = min(candidates, key=lambda item: item[:2])
            current.append((cost, substitutions, deletions, insertions))
        previous = current
    errors, substitutions, deletions, insertions = previous[-1]
    denominator = len(reference_words)
    return {
        "reference_words": denominator,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "errors": errors,
        "wer": errors / denominator if denominator else None,
    }


def score_pair(reference, hypothesis):
    normalized_reference, normalized_hypothesis = normalize(reference), normalize(hypothesis)
    return {
        "reference_raw": reference,
        "hypothesis_raw": hypothesis,
        "reference_normalized": normalized_reference,
        "hypothesis_normalized": normalized_hypothesis,
        **edit_counts(normalized_reference.split(), normalized_hypothesis.split()),
    }


def aggregate(scores):
    totals = {key: sum(score[key] for score in scores) for key in (
        "reference_words", "substitutions", "deletions", "insertions", "errors"
    )}
    totals["wer"] = totals["errors"] / totals["reference_words"] if totals["reference_words"] else None
    return totals


def object_fields(value, fields, path):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{path}: expected exactly fields {', '.join(fields)}")


def text(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: expected nonempty string")
    return value


def number(value, path, positive=False, integer=False):
    valid_type = type(value) is int if integer else type(value) in (int, float)
    if not valid_type or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{path}: expected finite {'positive' if positive else 'nonnegative'} number")
    return value


def hash_value(value, length, path):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is None:
        raise ValueError(f"{path}: expected lowercase {length}-hex digest")


def manifest_samples(manifest):
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Manifest schema_version must be 1")
    text(manifest.get("fixture_set_id"), "manifest.fixture_set_id")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Manifest requires samples")
    by_id = {}
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Manifest sample must be an object")
        identifier = text(sample.get("id"), "manifest.sample.id")
        if identifier in by_id:
            raise ValueError(f"Duplicate manifest sample: {identifier}")
        if sample.get("subset") not in SUBSETS:
            raise ValueError(f"Unknown manifest subset: {identifier}")
        if not normalize(sample.get("reference_raw")):
            raise ValueError(f"Empty normalized reference: {identifier}")
        number(sample.get("duration_seconds"), f"{identifier}.duration_seconds", positive=True)
        by_id[identifier] = sample
    return by_id


def validate_measurement(manifest, measurement):
    expected = manifest_samples(manifest)
    object_fields(measurement, (
        "schema_version", "fixture_set_id", "sdk", "environment", "runtime", "model",
        "readiness", "resources", "lifecycle", "samples",
    ), "measurement")
    if type(measurement["schema_version"]) is not int or measurement["schema_version"] != 1:
        raise ValueError("Measurement schema_version must be 1")
    if measurement["fixture_set_id"] != manifest["fixture_set_id"]:
        raise ValueError("Measurement fixture_set_id differs from manifest")
    object_fields(measurement["sdk"], ("git_sha",), "sdk")
    hash_value(measurement["sdk"]["git_sha"], 40, "sdk.git_sha")
    environment = measurement["environment"]
    object_fields(environment, ("os", "host_arch", "jvm_arch", "native_arch", "jdk_version", "jdk_vendor"), "environment")
    for key, value in environment.items():
        text(value, f"environment.{key}")
    assert_supported(environment["os"], environment["host_arch"])
    if environment["host_arch"] != environment["jvm_arch"] or environment["host_arch"] != environment["native_arch"]:
        raise ValueError("Host/JVM/native architectures must match")
    version = text(environment["jdk_version"], "jdk_version")
    if not re.match(r"^\d+(?:\.|$|[+-])", version) or int(re.split(r"[.+-]", version)[0]) < 17:
        raise ValueError("Measured JVM must be Java 17+")
    text(environment["jdk_vendor"], "jdk_vendor")
    for name, fields in (("runtime", ("version", "sha256")), ("model", ("id", "version", "sha256"))):
        object_fields(measurement[name], fields, name)
        hash_value(measurement[name]["sha256"], 64, f"{name}.sha256")
        for field in fields:
            if field != "sha256":
                text(measurement[name][field], f"{name}.{field}")
    readiness = measurement["readiness"]
    object_fields(readiness, ("status", "elapsed_ms", "cold_start"), "readiness")
    if readiness["status"] != "ready" or type(readiness["cold_start"]) is not bool:
        raise ValueError("Readiness requires ready status and explicit boolean cold_start")
    number(readiness["elapsed_ms"], "readiness.elapsed_ms")
    resources = measurement["resources"]
    object_fields(resources, (
        "peak_rss_bytes", "rss_method", "runtime_download_bytes", "model_download_bytes",
        "runtime_install_bytes", "model_install_bytes",
    ), "resources")
    text(resources["rss_method"], "resources.rss_method")
    for key in resources:
        if key != "rss_method":
            number(resources[key], f"resources.{key}", integer=True, positive=key in (
                "peak_rss_bytes", "runtime_install_bytes", "model_install_bytes"
            ))
    object_fields(measurement["lifecycle"], ("native_loaded", "cancel_verified", "cleanup_verified"), "lifecycle")
    if any(value is not True for value in measurement["lifecycle"].values()):
        raise ValueError("Actual native load, cancellation and cleanup evidence are all required")
    samples = measurement["samples"]
    if not isinstance(samples, list):
        raise ValueError("Measurement samples must be an array")
    seen = set()
    for sample in samples:
        object_fields(sample, ("id", "hypothesis_raw", "timing"), "sample")
        identifier = text(sample["id"], "sample.id")
        if identifier in seen or identifier not in expected:
            raise ValueError(f"Duplicate or unknown measured sample: {identifier}")
        seen.add(identifier)
        if not isinstance(sample["hypothesis_raw"], str):
            raise ValueError(f"{identifier}.hypothesis_raw: expected string (empty output is allowed)")
        timing = sample["timing"]
        object_fields(timing, (
            "mode", "audio_duration_ms", "feed_started_ms", "first_nonempty_ms", "input_closed_ms",
            "finalized_ms", "inference_wall_ms", "chunk_duration_ms",
        ), f"{identifier}.timing")
        if timing["mode"] != "paced":
            raise ValueError("Primary smoke measurement requires paced streaming")
        for field, value in timing.items():
            if field == "mode" or (field == "first_nonempty_ms" and value is None):
                continue
            number(value, f"{identifier}.{field}", positive=field in (
                "audio_duration_ms", "inference_wall_ms", "chunk_duration_ms"
            ))
        start, closed, final = (timing[key] for key in ("feed_started_ms", "input_closed_ms", "finalized_ms"))
        duration, chunk = timing["audio_duration_ms"], timing["chunk_duration_ms"]
        if not math.isclose(duration, expected[identifier]["duration_seconds"] * 1000, abs_tol=0.001, rel_tol=0):
            raise ValueError(f"{identifier}: measured duration differs from fixed WAV")
        if not start <= closed <= final:
            raise ValueError(f"{identifier}: timestamps must satisfy feed <= input-close <= final")
        if chunk > min(duration, 100) or closed - start + chunk + 1 < duration:
            raise ValueError(f"{identifier}: feeding was not paced at the source audio duration")
        if not math.isclose(timing["inference_wall_ms"], final - start, abs_tol=0.001, rel_tol=0):
            raise ValueError(f"{identifier}: inference_wall_ms must cover first feed through final result")
        first = timing["first_nonempty_ms"]
        if first is not None and not start <= first <= final:
            raise ValueError(f"{identifier}: first nonempty timestamp is outside inference interval")
        if first is None and sample["hypothesis_raw"].strip():
            raise ValueError(f"{identifier}: nonempty final hypothesis requires a first-nonempty timestamp")
    if seen != set(expected):
        raise ValueError(f"Missing measured samples: {', '.join(sorted(set(expected) - seen))}")
    return expected


def score_measurement(manifest, measurement):
    expected = validate_measurement(manifest, measurement)
    measured = {sample["id"]: sample for sample in measurement["samples"]}
    scores = []
    for identifier, reference in expected.items():
        sample = measured[identifier]
        timing = sample["timing"]
        first = timing["first_nonempty_ms"]
        scores.append({
            "id": identifier,
            "subset": reference["subset"],
            **score_pair(reference["reference_raw"], sample["hypothesis_raw"]),
            "first_nonempty_latency_ms": None if first is None else first - timing["feed_started_ms"],
            "finalization_latency_ms": timing["finalized_ms"] - timing["input_closed_ms"],
            "paced_rtf": timing["inference_wall_ms"] / timing["audio_duration_ms"],
        })
    return {
        "schema_version": 1,
        "fixture_set_id": manifest["fixture_set_id"],
        "evaluation_kind": "public-english-smoke-not-product-quality",
        "normalization_version": NORMALIZATION_VERSION,
        "unicode_database_version": unicodedata.unidata_version,
        "corpus": aggregate(scores),
        "subsets": {subset: aggregate([sample for sample in scores if sample["subset"] == subset]) for subset in SUBSETS},
        "samples": scores,
        "measurement_raw": copy.deepcopy(measurement),
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.manifest.resolve(), args.measurement.resolve()):
        raise ValueError("Report output must not overwrite raw evidence or references")
    report = score_measurement(load_json(args.manifest), load_json(args.measurement))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report["corpus"], allow_nan=False))


if __name__ == "__main__":
    main()
