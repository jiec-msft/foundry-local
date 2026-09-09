# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Bounded real CLI evaluation of the immutable public SDK; no transcript fallback."""

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from platform_checks import assert_identities, host_identity, jvm_identity, native_identity
from scorer import load_json, score_measurement

ROOT = Path(__file__).resolve().parent
SDK = ROOT.parent
SDK_SHA = "d0946a0764d9cfa4b3d684940d6d5c66165427b8"
JAR_SHA = "bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863"
JAR_BYTES = 64000
JNA_SHA = "b3a9408e7c51e08ef0e3bfcc08f443f6ec0f6191ba8cd7c18d53d2b22e5bdbc0"
JNA_BYTES = 2002589
NATIVE_LOCK = SDK / "src" / "main" / "resources" / "com" / "microsoft" / "foundry" / "local"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def unknown(reason):
    return {"value": None, "reason": reason}


def verify_model(cache, lock):
    candidates = [path.parent for path in cache.rglob("genai_config.json")]
    matches = []
    for directory in candidates:
        if all((directory / item["name"]).is_file() for item in lock["files"]):
            matches.append(directory)
    if len(matches) != 1:
        raise ValueError("Expected exactly one complete pinned model in the explicit cache")
    directory = matches[0]
    lines = []
    for item in sorted(lock["files"], key=lambda item: item["name"]):
        path = directory / item["name"]
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"Pinned model hash/size mismatch: {item['name']}")
        lines.append(f"{item['name']}\t{item['bytes']}\t{item['sha256']}\n")
    if hashlib.sha256("".join(lines).encode()).hexdigest() != lock["manifestSha256"]:
        raise ValueError("Model manifest hash mismatch")
    return sum(item["bytes"] for item in lock["files"])


def verify_artifacts(jar, runtime, target, java):
    jna = jar.parent / "lib" / "jna-5.17.0.jar"
    if (jar.stat().st_size != JAR_BYTES or jna.stat().st_size != JNA_BYTES
            or sha256(jar) != JAR_SHA or sha256(jna) != JNA_SHA):
        raise ValueError("Immutable SDK/JNA artifact size or hash mismatch")
    with zipfile.ZipFile(jar) as archive:
        versions = {struct.unpack(">H", archive.read(name)[6:8])[0] for name in archive.namelist() if name.endswith(".class")}
        if versions != {61}:
            raise ValueError(f"SDK must contain Java 17 bytecode only, got {versions}")
    expected_os, expected_arch = target.rsplit("-", 1)
    rid = {"windows": "win", "linux": "linux", "macos": "osx"}[expected_os] + "-" + expected_arch
    identities, hashes = [], {}
    for line in (NATIVE_LOCK / "native-lock.properties").read_text().splitlines():
        if not line.startswith(rid + "."):
            continue
        key, expected = line.split("=", 1)
        name = key[len(rid) + 1:]
        path = runtime / name
        if sha256(path) != expected:
            raise ValueError(f"Native lock mismatch: {name}")
        hashes[name] = expected
        identities.append(native_identity(path))
    host, jvm = host_identity(), jvm_identity(str(java))
    assert_identities(expected_os, expected_arch, host, jvm["jvm_arch"], identities)
    return {"os": host[0], "host_arch": host[1], "native_arch": expected_arch, **jvm}, rid, hashes


def rss_bytes(process):
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("page_faults", ctypes.c_ulong)] + [
                (name, ctypes.c_size_t) for name in ("peak_working", "working", "peak_paged", "paged",
                                                   "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")
            ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        function = ctypes.windll.psapi.GetProcessMemoryInfo
        function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not function(int(process._handle), ctypes.byref(counters), counters.cb):
            if process.poll() is not None:
                return None
            raise ctypes.WinError()
        return counters.peak_working
    if sys.platform.startswith("linux"):
        try:
            status = Path(f"/proc/{process.pid}/status").read_text()
        except FileNotFoundError:
            return None
        for line in status.splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
        return None
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(process.pid)], capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return int(result.stdout.strip()) * 1024


def stop_owned(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=True)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=10)


def run_cli(java, jar, arguments, output, name, deadline):
    remaining = min(300 if arguments[0] == "prepare" else 75, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("Evaluation batch deadline exhausted before starting another process")
    local = output / "local"
    local.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    peak = None
    command = [str(java)]
    if int(jvm_identity(str(java))["jdk_version"].split(".")[0]) >= 24:
        command.append("--enable-native-access=ALL-UNNAMED")
    command += ["-jar", str(jar), *arguments]
    environment = {**os.environ, "ORT_TELEMETRY_DISABLED": "1"}
    process = None
    timed_out = False
    with (local / f"{name}.stdout.jsonl").open("w", encoding="utf-8") as stdout, (
        local / f"{name}.stderr.txt"
    ).open("w", encoding="utf-8") as stderr:
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=environment,
                                       start_new_session=os.name != "nt")
            save(output / "active-process.json", {"pid": process.pid, "command": name})
            while process.poll() is None:
                observed = rss_bytes(process)
                if observed is not None:
                    peak = max(peak or 0, observed)
                if time.monotonic() - started >= remaining:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process is not None:
                stop_owned(process)
            save(output / "active-process.json", {"pid": None})
    events = []
    for line in (local / f"{name}.stdout.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    result = {"command": name, "exit_code": process.returncode, "timed_out": timed_out,
              "process_wall_ms": (time.monotonic() - started) * 1000,
              "peak_rss_bytes": peak, "events": events}
    # Raw process logs remain local; publish structured events only, never command paths.
    save(output / "local" / f"{name}.process.json", result)
    if timed_out or process.returncode != 0:
        raise RuntimeError(f"{name}: process failed (exit {process.returncode}, timed_out={timed_out}); local logs retained")
    if any(event["event"] == "error" for event in events):
        raise ValueError(f"{name}: native error event")
    return result


def event_once(run, name):
    events = [event for event in run["events"] if event["event"] == name]
    if len(events) != 1:
        raise ValueError(f"{run['command']}: expected one {name} event, found {len(events)}")
    return events[0]


def require_cleanup(run, inference=True):
    names = [event["event"] for event in run["events"]]
    required = ["result", "requestClosed", "modelUnloaded", "managerClosed"] if inference else ["managerClosed"]
    indices = [names.index(name) if names.count(name) == 1 else -1 for name in required]
    if -1 in indices or indices != sorted(indices):
        raise ValueError(f"{run['command']}: missing/duplicate/out-of-order cleanup events")
    if inference and event_once(run, "result")["processChildren"] != 0:
        raise ValueError("Unexpected inference child processes; process-tree cleanup not established")


def measured_sample(reference, run, cancelled=False):
    require_cleanup(run)
    result = event_once(run, "result")
    timing = result["timing"]
    if result["result"]["cancelled"] is not cancelled:
        raise ValueError("Observed cancellation state differs from requested operation")
    if not cancelled and timing["submittedBytes"] != reference["frames"] * 2:
        raise ValueError("Not all frozen WAV PCM frames were admitted by native input")
    if abs(result["audioSeconds"] - reference["duration_seconds"]) > 0.000001:
        raise ValueError("SDK audio duration differs from frozen WAV")
    if cancelled:
        requested, final = timing["cancellationRequestedMillis"], timing["finalizedMillis"]
        if requested is None or final is None or final < requested:
            raise ValueError("Cancellation request/acknowledgment not observed")
        if timing["inputClosedMillis"] is not None or result["result"]["text"]:
            raise ValueError("Early cancellation must not masquerade as natural close or final transcript")
        return {"verified": True, "cancellation_requested_ms": requested, "acknowledged_ms": final,
                "acknowledgment_latency_ms": final - requested, "natural_input_closed_ms": None,
                "submitted_bytes": timing["submittedBytes"], "cleanup_verified": True}
    first, final = timing["firstInputMillis"], timing["finalizedMillis"]
    if first is None or final is None:
        raise ValueError("Input admission/final response timestamps are required for completed inference")
    return {
        "id": reference["id"], "hypothesis_raw": result["result"]["text"],
        "timing": {
            "mode": "paced" if result["mode"] == "stream" else "batch",
            "audio_duration_ms": result["audioSeconds"] * 1000,
            "feed_started_ms": first, "first_nonempty_ms": timing["firstNonemptyMillis"],
            "input_closed_ms": timing["inputClosedMillis"], "finalized_ms": final,
            "inference_wall_ms": final - first, "chunk_duration_ms": result["chunkMillis"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("java", "jar", "runtime-dir", "cache-dir", "output"):
        parser.add_argument("--" + option, required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=840)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--accept-model-license", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 1000:
        raise ValueError("Batch timeout must be 1..1000 seconds")
    if args.output.exists():
        raise ValueError("Use a fresh output directory to preserve prior evidence")
    args.output.mkdir(parents=True)
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    deadline = started + args.timeout_seconds
    save(args.output / "run-summary.json", {
        "sdk_source_sha": SDK_SHA, "sdk_jar_sha256": JAR_SHA, "started_utc": started_utc,
        "finished_utc": None, "outcome": "running",
    })
    runs = []
    try:
        manifest = load_json(ROOT / "manifest.json")
        model_lock = load_json(SDK / "model-lock.json")
        environment, rid, natives = verify_artifacts(args.jar, args.runtime_dir, args.target, args.java)
        for sample in manifest["samples"]:
            if sha256(ROOT / sample["wav_path"]) != sample["wav_sha256"]:
                raise ValueError(f"Fixture hash mismatch: {sample['id']}")
        common = ["--runtime-dir", str(args.runtime_dir), "--cache-dir", str(args.cache_dir),
                  "--app-data-dir", str(args.output / "app-data"), "--model", model_lock["id"], "--json"]

        def invoke(command, name, extra=()):
            run = run_cli(args.java, args.jar, [command, *common, *extra], args.output, name, deadline)
            runtime = event_once(run, "runtime")
            if (runtime["version"], runtime["apiVersion"], runtime["nativeTarget"]) != ("2.0.1", 1, rid):
                raise ValueError("Actual native runtime handshake differs from pinned tuple")
            if runtime["javaVersion"] != environment["jdk_version"] or runtime["javaVendor"] != environment["jdk_vendor"]:
                raise ValueError("Actual inference JVM differs from measured JVM")
            model = event_once(run, "model")["model"]
            if model["id"] != model_lock["id"] or model["version"] != model_lock["version"] or (
                model["executionProvider"] != model_lock["executionProvider"]
            ):
                raise ValueError("Native exact model/version/provider differs from lock")
            runs.append(run)
            save(args.output / "partial.json", {"status": "running", "completed_commands": [r["command"] for r in runs]})
            return run

        identified = invoke("identify", "identify")
        # identify/prepare return inside the SDK's try-with-resources and emit no
        # managerClosed marker. Only inference commands establish explicit cleanup.
        if args.prepare:
            if not args.accept_model_license:
                raise ValueError("Explicit model-license acceptance required for prepare")
            prepared = invoke("prepare", "prepare", ["--explicit-download", "--accept-model-license"])
            if not event_once(prepared, "prepared")["cached"]:
                raise ValueError("Explicit preparation did not produce a cached model")
        installed = verify_model(args.cache_dir, model_lock)
        batch, paced = [], []
        for sample in manifest["samples"]:
            wav = str(ROOT / sample["wav_path"])
            batch.append(measured_sample(sample, invoke("transcribe", "batch-" + sample["id"], ["--wav", wav])))
            paced.append(measured_sample(sample, invoke("stream", "paced-" + sample["id"], ["--wav", wav, "--chunk-ms", "20"])))
        cancellation = measured_sample(manifest["samples"][0], invoke(
            "stream", "cancel", ["--wav", str(ROOT / manifest["samples"][0]["wav_path"]),
                                 "--chunk-ms", "20", "--cancel-after-ms", "1200"]), cancelled=True)
        peaks = [run["peak_rss_bytes"] for run in runs if run["peak_rss_bytes"] is not None]
        measurement = {
            "schema_version": 2, "fixture_set_id": manifest["fixture_set_id"], "sdk": {"git_sha": SDK_SHA},
            "environment": environment,
            "runtime": {"version": "2.0.1", "sha256": load_json(NATIVE_LOCK / "runtime-lock.json")["packages"][0]["sha256"]},
            "model": {"id": model_lock["id"], "version": str(model_lock["version"]), "sha256": model_lock["manifestSha256"]},
            "readiness": {
                "status": "ready", "elapsed_ms": unknown("No end-to-end readiness timestamp; model load durations retained separately"),
                "cold_start": not event_once(identified, "model")["cached"],
                "model_load_ms": [event_once(run, "loaded")["elapsedMillis"] for run in runs
                                                     if any(e["event"] == "loaded" for e in run["events"])],
            },
            "resources": {
                "peak_rss_bytes": max(peaks) if peaks else unknown("No process RSS observation available"),
                "rss_method": "Root JVM OS peak working set/VmHWM sampled every 100ms; macOS sampled RSS lower bound; no inference children observed",
                "runtime_download_bytes": unknown("Network transport not instrumented; verified runtime artifact sizes are not transfer bytes"),
                "model_download_bytes": unknown("Native API exposes percentages only; catalog may network even with cached weights"),
                "runtime_install_bytes": sum(p.stat().st_size for p in args.runtime_dir.rglob("*") if p.is_file()),
                "model_install_bytes": installed,
                "artifact_download_bytes": unknown("Local artifacts reused, or prepared by separate CI stage; actual network transfer not measured"),
                "sdk_artifact_bytes": args.jar.stat().st_size + (args.jar.parent / "lib" / "jna-5.17.0.jar").stat().st_size,
            },
            "lifecycle": {"native_loaded": True, "cancel_verified": True, "cleanup_verified": True},
            "samples": paced,
            "batch_samples": batch,
            "cancellation": cancellation,
            "provenance": {"sdk_jar_sha256": JAR_SHA, "jna_sha256": JNA_SHA, "native_sha256": natives,
                           "timing_origin": "Each result.timing is request-local monotonic; never mixed with CLI elapsedMillis",
                           "coverage": "10 batch WAV, 10 paced WAV/PCM, one early cancellation; native TOKEN events are deltas"},
        }
        save(args.output / "measurement.json", measurement)
        with (args.output / "events.jsonl").open("w", encoding="utf-8") as output:
            for run in runs:
                output.write(json.dumps(run, ensure_ascii=True) + "\n")
        report = score_measurement(manifest, measurement)
        save(args.output / "report.json", report)
        save(args.output / "platform.json", environment)
        save(args.output / "partial.json", {"status": "completed", "completed_commands": [r["command"] for r in runs],
                                          "active_processes": [], "compute_slot": "RELEASED"})
        save(args.output / "run-summary.json", {
            "sdk_source_sha": SDK_SHA, "sdk_jar_sha256": JAR_SHA, "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(), "outcome": "completed",
            "wall_seconds": time.monotonic() - started, "process_count": len(runs), "active_processes": [],
        })
        print(json.dumps({"status": "completed", "corpus": report["corpus"], "batch": report["batch"]["corpus"]}))
    except (ValueError, RuntimeError, OSError, TimeoutError, KeyboardInterrupt) as error:
        save(args.output / "partial.json", {"status": "failed", "error_type": type(error).__name__, "message": str(error),
                                          "completed_commands": [run["command"] for run in runs],
                                          "active_processes": [], "compute_slot": "RELEASED"})
        save(args.output / "run-summary.json", {
            "sdk_source_sha": SDK_SHA, "sdk_jar_sha256": JAR_SHA, "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(), "outcome": "failed",
            "wall_seconds": time.monotonic() - started, "process_count": len(runs), "active_processes": [],
        })
        raise


if __name__ == "__main__":
    main()
