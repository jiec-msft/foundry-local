# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Assert actual host, JVM, and individual native binary architectures."""

import argparse
import ctypes
import json
import platform
import re
import struct
import subprocess
from pathlib import Path


def normalize_arch(value):
    aliases = {"amd64": "x64", "x86_64": "x64", "x64": "x64", "aarch64": "arm64", "arm64": "arm64"}
    try:
        return aliases[value.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported architecture: {value}") from exc


def assert_supported(os_name, arch):
    if (os_name, arch) not in {
        ("windows", "x64"), ("windows", "arm64"),
        ("linux", "x64"), ("linux", "arm64"), ("macos", "arm64"),
    }:
        raise ValueError(f"Unsupported Foundry Local Java ASR target: {os_name}-{arch}")


def host_identity():
    os_name = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system())
    if os_name is None:
        raise ValueError(f"Unsupported host OS: {platform.system()}")
    if os_name == "windows":
        # GetNativeSystemInfo reports the host, even under an emulated Python process.
        buffer = ctypes.create_string_buffer(64)
        ctypes.windll.kernel32.GetNativeSystemInfo(buffer)
        code = int.from_bytes(buffer.raw[:2], "little")
        arch = {9: "x64", 12: "arm64"}.get(code)
        if arch is None:
            raise ValueError(f"Unsupported Windows processor architecture code: {code}")
    elif os_name == "macos":
        result = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True, check=True)
        arch = "arm64" if result.stdout.strip() == "1" else normalize_arch(platform.machine())
    else:
        arch = normalize_arch(platform.machine())
    assert_supported(os_name, arch)
    return os_name, arch


def jvm_identity(java="java"):
    result = subprocess.run(
        [java, "-XshowSettings:properties", "-version"], capture_output=True, text=True, check=True
    )
    properties = {}
    for line in (result.stdout + result.stderr).splitlines():
        match = re.match(r"\s*(os\.arch|java\.runtime\.version|java\.vendor)\s*=\s*(.+?)\s*$", line)
        if match:
            properties[match[1]] = match[2]
    if set(properties) != {"os.arch", "java.runtime.version", "java.vendor"}:
        raise ValueError("Cannot determine actual JVM architecture/version/vendor")
    major = int(properties["java.runtime.version"].split(".")[0].split("+")[0])
    if major < 17:
        raise ValueError(f"Java 17+ required; got {properties['java.runtime.version']}")
    return {
        "jvm_arch": normalize_arch(properties["os.arch"]),
        "jdk_version": properties["java.runtime.version"],
        "jdk_vendor": properties["java.vendor"],
    }


def native_identity(path):
    with Path(path).open("rb") as source:
        header = source.read(64)
        if header[:2] == b"MZ" and len(header) == 64:
            source.seek(struct.unpack_from("<I", header, 60)[0])
            pe = source.read(6)
            if pe[:4] != b"PE\0\0":
                raise ValueError("Invalid PE signature")
            machine = int.from_bytes(pe[4:6], "little")
            os_name, arch = "windows", {0x8664: "x64", 0xAA64: "arm64"}.get(machine)
        elif header[:4] == b"\x7fELF" and len(header) >= 20:
            if header[4:6] != b"\x02\x01":
                raise ValueError("Expected 64-bit little-endian ELF")
            machine = int.from_bytes(header[18:20], "little")
            os_name, arch = "linux", {62: "x64", 183: "arm64"}.get(machine)
        elif header[:4] == b"\xcf\xfa\xed\xfe" and len(header) >= 8:
            machine = int.from_bytes(header[4:8], "little")
            os_name, arch = "macos", {0x01000007: "x64", 0x0100000C: "arm64"}.get(machine)
        else:
            raise ValueError(f"Unsupported native format (including universal bundles): {path}")
    if arch is None:
        raise ValueError(f"Unsupported native machine code: {machine}")
    assert_supported(os_name, arch)
    return os_name, arch


def assert_identities(expected_os, expected_arch, host, jvm_arch, natives):
    assert_supported(expected_os, expected_arch)
    if host != (expected_os, expected_arch):
        raise ValueError(f"Host mismatch: expected {(expected_os, expected_arch)}, got {host}")
    if jvm_arch != expected_arch:
        raise ValueError(f"JVM architecture mismatch: expected {expected_arch}, got {jvm_arch}")
    if not natives:
        raise ValueError("At least one actual native binary is required")
    for native in natives:
        if native != host:
            raise ValueError(f"Native architecture mismatch: host {host}, native {native}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--os", required=True, choices=["windows", "linux", "macos"])
    parser.add_argument("--arch", required=True, choices=["x64", "arm64"])
    parser.add_argument("--java", default="java")
    parser.add_argument("--native", action="append", type=Path, required=True)
    args = parser.parse_args()
    host = host_identity()
    jvm = jvm_identity(args.java)
    natives = [native_identity(path) for path in args.native]
    assert_identities(args.os, args.arch, host, jvm["jvm_arch"], natives)
    print(json.dumps({"os": host[0], "host_arch": host[1], **jvm, "native_arch": args.arch}))


if __name__ == "__main__":
    main()
