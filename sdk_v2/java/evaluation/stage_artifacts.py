# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Stage only small evidence/JAR files; never upload runtimes, models or archives."""

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path


# Five lanes x 9 MB leaves 5 MB for a separately reviewed prerelease JAR/report.
LANE_LIMIT_BYTES = 9_000_000
ALLOWED_NAMES = {"measurement.json", "report.json", "events.jsonl", "platform.json", "sdk.jar"}


def stage_failure(source, destination):
    """Keep failed-lane evidence without exporting raw error messages or local paths."""
    if destination.exists():
        raise ValueError("Failure artifact destination must be fresh")
    processes = []
    for path in sorted((source / "local").glob("*.process.json")):
        process = json.loads(path.read_text(encoding="utf-8"))
        processes.append({
            "command": process["command"], "exit_code": process["exit_code"], "timed_out": process["timed_out"],
            "error_events": [{"error_type": event["errorType"], "code": event["code"]}
                             for event in process["events"] if event["event"] == "error"],
        })
    failure = {
        "status": "incomplete",
        "reason": "Integration or preparation failed; this is not a complete ASR measurement.",
        "processes": processes,
        "measurement_retained_locally": (source / "measurement.json").exists(),
        "raw_error_messages": "Not exported because native diagnostics can contain machine-specific paths.",
    }
    verification_path = source / "model-verification.json"
    if verification_path.exists():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        # Export only integrity metadata, never model contents or raw diagnostics.
        failure["model_verification"] = {
            key: verification[key]
            for key in ("status", "expected_manifest_sha256", "actual_manifest_sha256")
        }
        failure["model_verification"]["files"] = [
            {key: item[key] for key in (
                "name", "expected_bytes", "actual_bytes", "expected_sha256", "actual_sha256", "matched"
            )}
            for item in verification["files"]
        ]
    data = (json.dumps(failure, indent=2) + "\n").encode("utf-8")
    if len(data) > LANE_LIMIT_BYTES or re.search(rb"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:Users|home|runner)/", data):
        raise ValueError("Failure evidence exceeds privacy or size limits")
    destination.mkdir(parents=True)
    (destination / "failure.json").write_bytes(data)
    return len(data)


def stage(source, destination, limit=LANE_LIMIT_BYTES):
    if destination.exists():
        raise ValueError(f"Artifact staging must use a fresh destination: {destination}")
    files = [path for path in source.iterdir() if path.name in ALLOWED_NAMES]
    if not {"measurement.json", "report.json"}.issubset({path.name for path in files}):
        raise ValueError("Actual measurement.json and scored report.json are required")
    total = 0
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Expected regular artifact file: {path}")
        total += path.stat().st_size
        if path.suffix in (".json", ".jsonl"):
            content = path.read_text(encoding="utf-8")
            if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:Users|home|runner)/", content):
                raise ValueError(f"Machine-specific path in public evidence: {path.name}")
        if path.suffix == ".jar":
            with zipfile.ZipFile(path) as jar:
                prohibited = (".dll", ".so", ".dylib", ".onnx", ".nupkg", ".tar.gz")
                if any(name.lower().endswith(prohibited) or ".so." in name.lower() for name in jar.namelist()):
                    raise ValueError("Java JAR must not contain native/model/runtime bundles")
    if total > limit:
        raise ValueError(f"Artifact lane budget exceeded: {total} > {limit} bytes")
    destination.mkdir(parents=True)
    inventory = []
    for path in sorted(files):
        target = destination / path.name
        shutil.copyfile(path, target)
        inventory.append({
            "name": path.name, "bytes": target.stat().st_size,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
    inventory_bytes = (json.dumps(inventory, indent=2) + "\n").encode("utf-8")
    if total + len(inventory_bytes) > limit:
        raise ValueError("Artifact lane budget exceeded after checksum inventory")
    (destination / "SHA256SUMS.json").write_bytes(inventory_bytes)
    return total + len(inventory_bytes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--failure", action="store_true")
    args = parser.parse_args()
    operation = stage_failure if args.failure else stage
    print(f"Staged {operation(args.source, args.destination)} bytes")


if __name__ == "__main__":
    main()
