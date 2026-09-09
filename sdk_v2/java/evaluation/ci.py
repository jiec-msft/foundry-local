# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Fail-closed authorization and explicit fixed-SDK integration binding."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FULL_MATRIX_PREFIX = "Java ASR full-matrix "
RUNNERS = {
    "windows-x64": "windows-2022", "windows-arm64": "windows-11-arm",
    "linux-x64": "ubuntu-24.04", "linux-arm64": "ubuntu-24.04-arm", "macos-arm64": "macos-15",
}


def integration_command(args):
    command = [sys.executable, str(ROOT / "integration.py"), "--java", str(args.java),
               "--jar", str(args.jar), "--runtime-dir", str(args.runtime_dir),
               "--cache-dir", str(args.cache_dir), "--output", str(args.output),
               "--target", args.target, "--timeout-seconds", "840"]
    if args.prepare != args.accept_model_license:
        raise ValueError("Model preparation requires both --prepare and --accept-model-license")
    if args.prepare:
        command += ["--prepare", "--accept-model-license"]
    return command


def require_current_source(lock):
    if lock.get("source_pin_refresh_required") is not False:
        raise ValueError("BLOCKED: qualified SDK source-pin refresh and artifact-specific local evidence are required")


def validate_dispatch(lock, contract, context, previous_full_matrices):
    if context["repository"] != lock["repository"] or context["actor"] != lock["owner"]:
        raise ValueError("Only the public fork owner can dispatch this evaluation")
    if context["ref"] != lock["allowed_ref"]:
        raise ValueError("Evaluation dispatch ref is not allowlisted")
    if context["run_attempt"] != 1:
        raise ValueError("Do not rerun whole jobs: dispatch only failed lanes after a concrete fix")
    require_current_source(lock)
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
    if {t["id"]: t["runner"] for t in contract["supported_targets"]} != RUNNERS:
        raise ValueError("Only the five pinned standard public runners are permitted")
    if (lock["maximum_full_matrices"] != 2 or lock["max_parallel"] != 2
            or lock["job_timeout_minutes"] != 20 or lock["cache_enabled"] is not False):
        raise ValueError("Evaluation resource budget must remain fixed")
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


def validate_failed_lane(history, context):
    if context["lane"] == "full-matrix":
        return
    run_id = os.environ.get("FAILED_RUN_ID", "")
    if not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("Single-lane dispatch requires a prior failed run ID")
    runs = [r for page in history for r in page["workflow_runs"] if str(r["id"]) == run_id]
    if len(runs) != 1 or runs[0].get("head_branch") != context["ref"].removeprefix("refs/heads/"):
        raise ValueError("Failed run must belong to this workflow and allowlisted branch")
    jobs_pages = json.loads(subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp",
         f"repos/{context['repository']}/actions/runs/{run_id}/jobs?per_page=100"], text=True))
    jobs = [j for page in jobs_pages for j in page["jobs"]]
    if not any(j["name"] == "model-" + context["lane"] and j["conclusion"] in ("failure", "timed_out")
               for j in jobs):
        raise ValueError("Only a proven failed lane may be retried")
    subprocess.run(["git", "merge-base", "--is-ancestor", context["fix_sha"], "HEAD"], check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", runs[0]["head_sha"], context["fix_sha"]], check=True)
    if context["fix_sha"] == runs[0]["head_sha"]:
        raise ValueError("Fix commit must follow the failed run")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    guard = subparsers.add_parser("guard")
    guard.add_argument("--history", type=Path, required=True)
    guard.add_argument("--output", type=Path, required=True)
    integration = subparsers.add_parser("integration")
    integration.add_argument("--target", required=True, choices=RUNNERS)
    for option in ("java", "jar", "runtime-dir", "cache-dir", "output"):
        integration.add_argument("--" + option, required=True, type=Path)
    integration.add_argument("--prepare", action="store_true")
    integration.add_argument("--accept-model-license", action="store_true")
    args = parser.parse_args()
    if args.command == "integration":
        require_current_source(json.loads((ROOT / "ci-lock.json").read_text(encoding="utf-8")))
        raise SystemExit(subprocess.call(integration_command(args), env={**os.environ, "ORT_TELEMETRY_DISABLED": "1"}))
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
    validate_failed_lane(history, context)
    with args.output.open("a", encoding="utf-8") as output:
        output.write("matrix=" + json.dumps({"include": matrix}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
