# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Fail-closed CI preparation gates. No SDK adapter is bound in this revision."""

import argparse
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FULL_MATRIX_PREFIX = "Java ASR full-matrix "


def validate_dispatch(lock, contract, context, previous_full_matrices):
    if context["repository"] != lock["repository"] or context["actor"] != lock["owner"]:
        raise ValueError("Only the public fork owner can dispatch this evaluation")
    if context["ref"] != lock["allowed_ref"]:
        raise ValueError("Evaluation dispatch ref is not allowlisted")
    if context["run_attempt"] != 1:
        raise ValueError("Do not rerun whole jobs: dispatch only failed lanes after a concrete fix")
    if not all(lock[key] is True for key in (
        "enabled", "dispatch_authorized", "integration_adapter_ready", "dependency_license_review_complete"
    )):
        raise ValueError("BLOCKED: fixed SDK integration, license review, local Windows success and dispatch permission required")
    sha = context["sdk_sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or sha != lock["sdk_git_sha"] or sha != contract["sdk_git_sha"]:
        raise ValueError("SDK SHA must be the immutable reviewed handoff recorded in both locks")
    evidence = lock["local_windows_evidence"]
    if not isinstance(evidence, dict) or evidence.get("sdk_git_sha") != sha:
        raise ValueError("Matching local Windows SDK success evidence is required before CI")
    if not re.fullmatch(r"[0-9a-f]{64}", evidence.get("sha256", "")):
        raise ValueError("Local Windows evidence must have a reviewed SHA256")
    if not isinstance(lock["model"], dict) or not re.fullmatch(r"[0-9a-f]{64}", lock["model"].get("sha256", "")):
        raise ValueError("A fixed public model with a SHA256 is required")
    for dependency in contract["runtime"]["dependencies"]:
        if not re.fullmatch(r"[0-9a-f]{64}", dependency["sha256"] or ""):
            raise ValueError(f"Missing pinned public dependency hash: {dependency['package']}")
    targets = {target["id"] for target in contract["supported_targets"]}
    lane = context["lane"]
    if lane == "full-matrix":
        if previous_full_matrices >= lock["maximum_full_matrices"]:
            raise ValueError("Two full matrices exhausted; stop and review (failed lanes only after fixes)")
    elif lane not in targets:
        raise ValueError(f"Unknown lane: {lane}")
    elif not re.fullmatch(r"[0-9a-f]{40}", context["fix_sha"]) or not context["fix_reason"].strip():
        raise ValueError("A failed-lane dispatch requires a concrete fix commit and explanation")
    return [target for target in contract["supported_targets"] if lane == "full-matrix" or lane == target["id"]]


def previous_full_count(pages, current_run_id):
    runs = [run for page in pages for run in page["workflow_runs"]]
    return len({
        run["id"] for run in runs
        if str(run["id"]) != str(current_run_id) and run["display_title"].startswith(FULL_MATRIX_PREFIX)
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    guard = subparsers.add_parser("guard")
    guard.add_argument("--history", type=Path, required=True)
    guard.add_argument("--output", type=Path, required=True)
    integration = subparsers.add_parser("integration")
    integration.add_argument("--target", required=True)
    args = parser.parse_args()
    if args.command == "integration":
        raise SystemExit(
            "BLOCKED: immutable SDK launcher/JSONL event schema and explicit preparation adapter "
            "must be integrated after local compute permission. No model has been run."
        )
    lock = json.loads((ROOT / "ci-lock.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "sdk-contract.json").read_text(encoding="utf-8"))
    context = {
        "repository": os.environ["GITHUB_REPOSITORY"],
        "actor": os.environ["GITHUB_ACTOR"],
        "ref": os.environ["GITHUB_REF"],
        "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
        "sdk_sha": os.environ["SDK_SHA"],
        "lane": os.environ["LANE"],
        "fix_sha": os.environ["FIX_SHA"],
        "fix_reason": os.environ["FIX_REASON"],
    }
    history = json.loads(args.history.read_text(encoding="utf-8"))
    matrix = validate_dispatch(lock, contract, context, previous_full_count(history, os.environ["GITHUB_RUN_ID"]))
    with args.output.open("a", encoding="utf-8") as output:
        output.write("matrix=" + json.dumps({"include": matrix}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
