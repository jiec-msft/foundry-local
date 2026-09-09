# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Explicit pinned public tool bootstrap, reproducible thin JAR build and native preparation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

from model_inventory import METADATA_SHA, load_model_metadata
from platform_checks import host_identity, native_identity, native_rid

ROOT = Path(__file__).resolve().parent
SDK = ROOT.parent
BUILD = ROOT / "build" / "ci"


def verify(path, pin):
    algorithm = "sha256" if "sha256" in pin else "sha512"
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != pin[algorithm] or ("bytes" in pin and path.stat().st_size != pin["bytes"]):
        raise ValueError(f"Pinned artifact mismatch: {path.name}; refusing substitution")


def download(pin, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        part = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(pin["url"], timeout=60) as source, part.open("wb") as output:
                shutil.copyfileobj(source, output)
            verify(part, pin)
            part.replace(destination)
        finally:
            part.unlink(missing_ok=True)
    verify(destination, pin)


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if not (destination / member.filename).resolve().is_relative_to(destination.resolve()):
                    raise ValueError("Unsafe archive member")
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")


def verify_jar(jar, contract):
    verify(jar, contract["sdk_jar"])
    verify(jar.parent / "lib" / "jna-5.17.0.jar", contract["jna"])
    with zipfile.ZipFile(jar) as bundle:
        classes = [name for name in bundle.namelist() if name.endswith(".class")]
        if not classes:
            raise ValueError("SDK JAR contains no bytecode")
        for name in classes:
            data = bundle.read(name)
            if data[:4] != b"\xca\xfe\xba\xbe" or int.from_bytes(data[6:8], "big") != 61:
                raise ValueError("SDK must retain Java17 bytecode on every JDK")
        if any(name.lower().endswith((".dll", ".so", ".dylib", ".onnx")) for name in bundle.namelist()):
            raise ValueError("SDK must be a thin JAR")


def prepare(args):
    tools = json.loads((ROOT / "ci-tools-lock.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "sdk-contract.json").read_text(encoding="utf-8"))
    target = next(t for t in contract["supported_targets"] if t["id"] == args.target)
    host = host_identity()
    if host != (target["os"], target["arch"]):
        raise ValueError("Actual host does not match requested standard runner lane")
    metadata = load_model_metadata(contract)
    rid = native_rid(*host)
    if target["rid"] != rid:
        raise ValueError("Preparation target RID differs from verified native host")
    metadata.select(rid)
    pin = tools["jdk"][args.target]
    archive = BUILD / "downloads" / ("jdk.zip" if target["os"] == "windows" else "jdk.tar.gz")
    download(pin, archive)
    unpack(archive, BUILD / "jdk")
    executable = "java.exe" if target["os"] == "windows" else "java"
    candidates = [p for p in (BUILD / "jdk").rglob(executable) if p.parent.name == "bin"]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one pinned JDK")
    java = candidates[0]
    if native_identity(java) != (target["os"], target["arch"]):
        raise ValueError("JDK executable architecture mismatch; no emulation permitted")
    version = subprocess.check_output([str(java), "-version"], stderr=subprocess.STDOUT, text=True)
    if f'"{pin["version"].split("+")[0]}' not in version:
        raise ValueError("JDK version mismatch")
    environment = {**os.environ, "JAVA_HOME": str(java.parent.parent),
                   "PATH": str(java.parent) + os.pathsep + os.environ["PATH"],
                   "ORT_TELEMETRY_DISABLED": "1"}
    if args.sdk_jar:
        jar = args.sdk_jar.resolve()
        verify(jar, contract["sdk_jar"])
        download(contract["jna"], jar.parent / "lib" / "jna-5.17.0.jar")
    else:
        if pin["major"] != 17 or args.target != "windows-x64":
            raise ValueError("Build the fixed artifact on Windows x64 JDK17; reuse that thin JAR on every native lane")
        maven_archive = BUILD / "downloads" / "maven.zip"
        download(tools["maven"], maven_archive)
        unpack(maven_archive, BUILD / "maven")
        maven = BUILD / "maven" / "apache-maven-3.9.9"
        # Invoke Maven's Java bootstrap directly, avoiding platform shell/quoting differences.
        launcher = next((maven / "boot").glob("plexus-classworlds-*.jar"))
        command = [str(java), f"-Dmaven.home={maven}", f"-Dmaven.multiModuleProjectDirectory={SDK}",
                   f"-Dclassworlds.conf={maven / 'bin' / 'm2.conf'}", "-classpath", str(launcher),
                   "org.codehaus.plexus.classworlds.launcher.Launcher", "--batch-mode", "--no-transfer-progress",
                   "-f", str(SDK / "pom.xml"), f"-Dmaven.repo.local={BUILD / 'm2'}", "clean", "package"]
        subprocess.run(command, check=True, env=environment)
        jar = SDK / "target" / contract["sdk_jar"]["name"]
    verify_jar(jar, contract)
    if args.build_only:
        with args.output.open("a", encoding="utf-8") as output:
            output.write(f"jar={jar}\n")
        return
    runtime = BUILD / "runtime"
    subprocess.run([sys.executable, str(SDK / "scripts" / "prepare_runtime.py"),
                    "--runtime-dir", str(runtime), "--cache-dir", str(BUILD / "native-downloads"),
                    "--rid", target["rid"], "--explicit-download", "--accept-native-licenses"], check=True)
    from integration import verify_artifacts
    _, verified_rid, _ = verify_artifacts(jar, runtime, args.target, java)
    selected = metadata.select(verified_rid)
    with args.output.open("a", encoding="utf-8") as output:
        for key, value in {"java": java, "jar": jar, "runtime": runtime,
                           "model_cache": BUILD / "model-cache", "metadata_git_sha": METADATA_SHA,
                           "inventory_rid": verified_rid,
                           "model_manifest_sha256": selected["manifestSha256"],
                           "expected_model_install_bytes": selected["installedBytes"]}.items():
            output.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sdk-jar", type=Path)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--explicit-download", action="store_true", required=True)
    parser.add_argument("--accept-native-licenses", action="store_true", required=True)
    args = parser.parse_args()
    prepare(args)


if __name__ == "__main__":
    main()
