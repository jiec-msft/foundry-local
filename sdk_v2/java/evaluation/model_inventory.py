# Copyright (c) Microsoft Corporation. Licensed under the MIT License.
"""Consume the immutable SDK metadata selector without changing binary-source provenance."""

import hashlib
import json
from pathlib import Path
import subprocess
import types

SDK = Path(__file__).resolve().parent.parent
SDK_SHA = "d0946a0764d9cfa4b3d684940d6d5c66165427b8"
METADATA_SHA = "38bbca7f4943687cd90d4aecc365424bb914957e"
METADATA_FILES = ("model-target-lock.json", "model-target-lock.schema.json", "scripts/model_lock.py")
BINARY_SOURCE_PATHS = (
    "sdk_v2/java/pom.xml", "sdk_v2/java/src", "sdk_v2/java/THIRD_PARTY_NOTICES.md",
    "sdk_v2/java/scripts/prepare_runtime.py", "sdk_v2/java/model-lock.json",
    "sdk_v2/java/API.md", "sdk_v2/java/cli.schema.json", "LICENSE",
)


def require_metadata_pin(contract):
    if contract.get("metadata_git_sha") != METADATA_SHA:
        raise ValueError("Metadata SHA must equal the separately reviewed immutable metadata revision")


def verify_binary_source(contract, sdk=SDK):
    if contract.get("sdk_git_sha") != SDK_SHA:
        raise ValueError("Binary source must remain bound to the qualified d094 SDK")
    subprocess.run(["git", "diff", "--exit-code", SDK_SHA, "--", *BINARY_SOURCE_PATHS],
                   cwd=sdk.parents[1], check=True, capture_output=True)


def validate_target_schema(document, schema):
    # Test-Json is already present with PowerShell on every approved runner.
    command = (
        "$ErrorActionPreference='Stop'; "
        "$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json; "
        "if (-not (Test-Json -Json $payload.document -Schema $payload.schema)) { exit 1 }"
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        input=json.dumps({"document": json.dumps(document), "schema": json.dumps(schema)}),
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise ValueError("Target inventory failed the pinned JSON Schema validation")


class ModelMetadata:
    def __init__(self, base, targets, selector, file_hashes):
        self.base = base
        self.targets = targets
        self.selector = selector
        self.file_hashes = file_hashes

    def select(self, native_rid):
        return self.selector(self.base, self.targets, native_rid)

    def provenance(self, selected, installed_bytes):
        if installed_bytes != selected["installedBytes"]:
            raise ValueError("Actual installed bytes differ from the selected target inventory")
        return {
            "native_rid": selected["inventoryTarget"],
            "manifest_sha256": selected["manifestSha256"],
            "installed_bytes": installed_bytes,
            "files_sha256": dict(self.file_hashes),
        }


def load_model_metadata(contract, sdk=SDK):
    require_metadata_pin(contract)
    verify_binary_source(contract, sdk)
    subprocess.run(
        ["git", "diff", "--exit-code", METADATA_SHA, "--",
         *(f"sdk_v2/java/{name}" for name in METADATA_FILES)],
        cwd=sdk.parents[1], check=True, capture_output=True,
    )

    def blob(revision, name):
        return subprocess.check_output(
            ["git", "show", f"{revision}:sdk_v2/java/{name}"], cwd=sdk.parents[1]
        )

    # Consume the pinned Git blobs themselves, not mutable worktree files or cached pyc.
    sources = {name: blob(METADATA_SHA, name) for name in METADATA_FILES}
    base = json.loads(blob(SDK_SHA, "model-lock.json"))
    targets = json.loads(sources["model-target-lock.json"])
    schema = json.loads(sources["model-target-lock.schema.json"])
    validate_target_schema(targets, schema)
    selector = types.ModuleType("reviewed_sdk_model_lock")
    exec(compile(sources["scripts/model_lock.py"], "model_lock.py@" + METADATA_SHA, "exec"),
         selector.__dict__)
    return ModelMetadata(base, targets, selector.select_model_inventory, {
        name: hashlib.sha256(data).hexdigest() for name, data in sources.items()
    })
