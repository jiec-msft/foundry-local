# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Re-score retained actual process evidence without rerunning or downloading a model."""

import argparse
import json
from pathlib import Path

from integration import ROOT, event_once, measured_sample, save
from scorer import load_json, score_measurement


def finalize(output):
    manifest = load_json(ROOT / "manifest.json")
    measurement = load_json(output / "measurement.json")
    runs = [load_json(output / "local" / "identify.process.json")]
    prepared = output / "local" / "prepare.process.json"
    if prepared.exists():
        runs.append(load_json(prepared))
    observed = {"batch_samples": [], "samples": []}
    for sample in manifest["samples"]:
        for prefix, field in (("batch", "batch_samples"), ("paced", "samples")):
            run = load_json(output / "local" / f"{prefix}-{sample['id']}.process.json")
            observed[field].append(measured_sample(sample, run))
            runs.append(run)
    cancel = load_json(output / "local" / "cancel.process.json")
    runs.append(cancel)
    if any(run["exit_code"] != 0 or run["timed_out"] for run in runs):
        raise ValueError("Cannot finalize failed or timed-out native process evidence")
    if any(any(event["event"] == "error" for event in run["events"]) for run in runs):
        raise ValueError("Cannot finalize a native error event")
    for field, samples in observed.items():
        if measurement[field] != samples:
            raise ValueError(f"{field} differs from actual authoritative native results/timestamps")
    if measurement["cancellation"] != measured_sample(manifest["samples"][0], cancel, cancelled=True):
        raise ValueError("Cancellation differs from actual retained event evidence")
    for run in runs:
        native = event_once(run, "runtime")
        if native["version"] != measurement["runtime"]["version"] or native["apiVersion"] != 1:
            raise ValueError("Retained native identity mismatch")
        if event_once(run, "model")["model"]["id"] != measurement["model"]["id"]:
            raise ValueError("Retained exact-model identity mismatch")
    report = score_measurement(manifest, measurement)
    save(output / "report.json", report)
    save(output / "platform.json", measurement["environment"])
    with (output / "events.jsonl").open("w", encoding="utf-8") as stream:
        for run in runs:
            stream.write(json.dumps(run, ensure_ascii=True) + "\n")
    original = output / "partial.json"
    if original.exists() and not (output / "initial-partial.json").exists():
        save(output / "initial-partial.json", load_json(original))
    save(original, {"status": "completed", "native_execution": "22 successful processes; no inference rerun",
                    "report_finalization": "Regenerated from retained raw processes and validated measurement",
                    "active_processes": [], "compute_slot": "RELEASED"})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = finalize(args.output)
    print(json.dumps({"corpus": report["corpus"], "batch": report["batch"]["corpus"]}))
