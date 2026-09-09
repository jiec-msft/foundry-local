# Fresh d094 Windows Java17 evaluation

This is fresh, artifact-specific evidence for public SDK source
`d0946a0764d9cfa4b3d684940d6d5c66165427b8`, not a relabeling of the separate
[06bf observations](LOCAL_EVALUATION.md). Ten English development utterances
remain a smoke set, never a product quality claim.

## Artifact and execution boundary

Before execution, the evaluator copied the qualified 64,000-byte SDK JAR and
separate 2,002,589-byte JNA5.17.0 JAR into its own ignored directory, scoped by
the full SDK source SHA and SDK JAR SHA256. Both copies were verified by size
and SHA256 and marked read-only. No execution used the SDK owner's mutable
target JAR. Existing public JDK/runtime/model-cache artifacts were reused.
No corpus expansion, model change or model/runtime download was requested.

| Artifact | SHA256 |
|---|---|
| SDK JAR | `bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863` |
| JNA JAR | `b3a9408e7c51e08ef0e3bfcc08f443f6ec0f6191ba8cd7c18d53d2b22e5bdbc0` |

The existing integration path ran **once**: identity, ten batch WAVs, ten
20 ms paced WAV/PCM streams, and one early cancellation. All22 native CLI
processes exited0. Every inference had `requestClosed`, `modelUnloaded`,
`managerClosed`, and no reported child process. All955 raw CLI events decoded
as strictUTF8 and passed the SDK JSONL schema. Final native aggregate text,
not reconstructed TOKEN deltas, supplied the scored hypotheses.

The `evaluation-d094-refresh-local-v1` slot was granted from
02:37:48.151 through02:52:48.151 +08:00 on2026-09-10. Native execution started
02:41:44.702 and finished02:45:02.859 (198.156 seconds). In addition to the
existing per-process75-second watchdog, an enclosing watchdog covered the
specific integration process tree with a02:52:18 deadline; it did not fire.
The CI wrapper now exposes `--timeout-seconds` so local callers can forward
the remaining slot budget directly. No second smoke or extra late-cancel
inference probe was started.

## Fresh measurements

| Observation | Result |
|---|---|
| Actual OS / host / JVM / native | Windows / x64 / x64 / x64 |
| JVM | Eclipse Adoptium Temurin17.0.20.1+1 |
| Bytecode / runtime | Java17 class major61 / Foundry2.0.1 packaged API1 |
| Exact model | nemotron-3.5-asr-streaming-0.6b-generic-cpu:3, CPUExecutionProvider |
| Batch WAV WER | 8/151 =5.298%;5 substitutions,0 deletions,3 insertions |
| Paced WER | 8/151 =5.298%;5 substitutions,0 deletions,3 insertions |
| Clean / other, each mode | 3/62 =4.839% /5/89 =5.618% |
| First nonblank native callback | 1250.155-2366.994 ms after native input admission |
| Natural close to finalization | 159.367-302.809 ms |
| Paced RTF | 1.0211-1.0736, including intentional pacing waits |
| Cancellation request / acknowledgment | 1228.314 /1312.690 ms, request-local origin |
| Cancellation acknowledgment latency | 84.377 ms;38,400 PCM bytes admitted; natural input close null |
| Observed peak root-JVM RSS | 1,065,725,952 bytes |
| Model-load durations | 1796-2915 ms, separately observed |
| Installed model / runtime files | 793,344,452 /35,772,965 bytes |
| SDK plus JNA artifact bytes | 2,066,589 bytes, not a network-transfer measurement |

End-to-end readiness and actual runtime/model/artifact network transfer bytes
remain unknown with explicit reasons in measurement version2. Native model
download reports percentages only. A populated model cache does not prove
network isolation: public catalog API1 may still network. `cold_start: false`
describes that model-cache state; each CLI operation used a fresh JVM.

## Isolated canonical rebuild

Within the same slot, the evaluator copied the unchanged integrated SDK source
and a37,764,603-byte snapshot of the existing public Maven cache into a separate
ignored build directory. It reused the existing public Temurin17/Maven3.9.9
tools and ran Maven **offline**, with all tests skipped to prevent additional
native work. This did not overwrite the qualified copy or any SDK-owner file.

The rebuild started02:46:33.476 and finished02:46:43.401, exited0, and produced
exactly64,000 bytes with SHA256
`bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863`.
No different JAR was repacked or relabeled. The temporary Maven-cache snapshot
was removed after the result was recorded; original caches remain intact.
The compute slot was released before02:46:44, with no owned native/build
processes remaining. This is local canonical reproducibility, not a hosted run.

## Small retained evidence

Structured evidence resides in
`build/windows-java17-d094-artifacts/`:203,272 bytes, or203,830 with the checksum
inventory. It has no machine-specific paths. Raw process diagnostics, app data,
run timestamps and watchdog metadata remain in `build/windows-java17-d094-run1/`.
Rebuild diagnostics remain in `build/canonical-d094/`. None was uploaded.

| Structured artifact | SHA256 |
|---|---|
| report.json | `840d0cececf14f93f6db7251cb85480e0ec774b407164121304a6c50cd8b6eb5` |
| measurement.json | `c413c9cd44b4807f8f29677b8ae96122eadb3dfef5e9afc752fa89852d43dc93` |
| events.jsonl | `3e5b624927514d70e2289fc19f06cfe461fcc96560eea2e31d1126561587dc4a` |
| platform.json | `776d6e0d74512d87ae7e065785dda0ca7028f61802542b8cb16b8f49c14e21ca` |

## First hosted matrix

The coordinator dispatched
[run34396100361](https://github.com/jiec-msft/foundry-local/actions/runs/34396100361)
exactly once, executing `b14d37fdc848777b1ff744a5d960e3940c3d3aae` with the same
qualified SDK source/JAR above. It ran from 2026-09-09T19:36:49Z through
19:42:20Z and concluded **failure**. This section is hosted evidence, not a
replacement or relabeling of the preceding local measurements.

| Job/lane | Actual outcome |
|---|---|
| authorize | Passed owner/ref/source/license/budget gates |
| build-sdk | Reproduced the exact 64,000-byte qualified JAR; Java17 bytecode |
| windows-2022 x64 | Native10WAV +10paced +cancel/cleanup passed |
| windows-11-arm ARM64 | Native10WAV +10paced +cancel/cleanup passed |
| ubuntu-24.04 x64 | Native identify/prepare exited0; model hash gate failed before ASR |
| ubuntu-24.04-arm ARM64 | Native identify/prepare exited0; model hash gate failed before ASR |
| macos-15 ARM64 | Native identify/prepare exited0; model hash gate failed before ASR |

Every lane ran preparation and entered the integration step; none was skipped.
The three failures occurred after native/JVM architecture and runtime identity
checks, at `verify_model`, not in the builder or tool/native preparation.
Their exported failure records contain only identify/prepare success and an
explicit incomplete status; no transcripts or complete measurements exist for
those lanes. They are **not** native ASR successes.

Both Windows artifacts contain23 successful CLI process records and1353
strictUTF8/schema-valid events, including request/model/manager cleanup and no
inference children. Actual host/JVM/native architecture matches each runner.
x64 uses Eclipse Adoptium17.0.20.1+1; ARM64 uses Microsoft17.0.20.1+1-LTS.
Native file hashes, runtime2.0.1/API1, CPU model identity and installed-file
manifest match the locks. Independent rescoring reproduces **8/151 edits
(5.298%)** in each mode and lane:5 substitutions,0 deletions,3 insertions;
dev-clean3/62 and dev-other5/89.

| Hosted metric | Windows x64 | Windows ARM64 |
|---|---|---|
| First-nonempty latency range, ms | 1304.7034-2419.4457 | 1274.8833-2394.2361 |
| Finalization latency range, ms | 209.3097-329.6811 | 187.7381-278.9533 |
| Paced RTF range | 1.022319-1.074251 | 1.019370-1.063078 |
| Cancellation acknowledgment, ms | 106.3618 | 85.3720 |
| Root JVM peak RSS, bytes | 1,040,027,648 | 1,012,781,056 |
| Report bundle including inventory, bytes | 225,964 | 225,833 |

Readiness and actual network-transfer bytes remain unknown with reasons. Artifact
storage sizes are not network-transfer measurements. Six artifacts total107,763
API-reported compressed bytes and517,336 extracted payload bytes, with seven-day
retention. They contain only the thin JAR, two successful small evidence bundles,
and three513-byte failure records; no model/runtime/corpus archives.

| Hosted evidence | SHA256 |
|---|---|
| Windows x64 report.json | `b0dc9c3f2d7c64ff5ce065907dd5499708f1818e7e0e671b32c8228f6ca04889` |
| Windows x64 measurement.json | `d902abbc0b8a85228e730bf0bb6a61bd6e686465fe705c7e01206cfd268ebcfc` |
| Windows x64 events.jsonl | `dc733af32b2ae184dd9ff3008daf2904caf222678057e252ef4bcfe11ff5b684` |
| Windows ARM64 report.json | `349d75f76b0a82f759a328349190adf401654f58297b06c6b3995279b6cc8cfe` |
| Windows ARM64 measurement.json | `023e33adc9cef97fa199313e675fa54ee3f7e453218b4d1cb5648523e78d81b5` |
| Windows ARM64 events.jsonl | `6acf2f8547460e57993c89e2bfd0ffdbf47b56aba219f2c33a8d0568ba9a46f2` |
| Each incomplete failure.json | `7f37c0cbc04a3b69fa0b73351517ffd3716443c15dddcfa8a129796c35ec3e72` |

### Failure diagnosis and next gate

All three failures report `Pinned model hash/size mismatch: inference_model.json`.
The public `sdk_v2/cpp/src/download/inference_model_writer.cc` writes this
generated cache marker through a text-mode stream. Independently reproducing its
two-field JSON with the locked model ID and null prompt template gives exactly
the Windows pin:90 CRLF bytes, SHA256
`881e9c5b34349dabe826cf88857835d15623c1a92a311d002812c399fe1128ef`.
The LF serialization is87 bytes, SHA256
`9bb2dbe6766fb9a5e3e1c8407a88141a480363d0aca7d4df4f88aa3e0399adeb`.
This is a source-supported platform-line-ending hypothesis, **not an observation
of the failed runners' files**: the first-run artifacts omitted actual mismatch
sizes/hashes. The packaged API1 binary is not qualified by newer public source
alone. Files sorted after the marker were not reached by the old verifier.

The diagnostic fix records every locked file's observed size/SHA256 and the
actual manifest digest before rejecting a mismatch; failure staging exports only
that bounded integrity metadata. Offline regressions retain rejection of LF
versus CRLF, altered manifests and unsafe output paths. No pin was changed,
normalization accepted, model content uploaded, or SDK source modified. This
fix improves diagnosis; it does **not** make the three failed lanes qualified.

Coordinator review is required before further hosted work or any portable
generated-marker lock change. One of at most two full matrices is consumed;
failed-lane dispatches require `failed_run_id=34396100361`, exact failed `lane`,
reviewed descendant `fix_sha` and concrete `fix_reason`. No rerun/dispatch,
repository setting, default-main, PR or release mutation was made by this
evaluator. No local native, build or model-download work occurred during observation.
Evaluation-only license scope and the unresolved catalog/card/notices discrepancy
remain unchanged; model/native redistribution and production deployment are
not authorized. This ten-utterance smoke makes no product-quality, plugin,
microphone or hardware-generation coverage claim.

## Linux x64 diagnostic inventory

The coordinator dispatched one diagnostic failed-lane run,
[34398826339](https://github.com/jiec-msft/foundry-local/actions/runs/34398826339),
executing `e7fa302b54fe410d762bd47965fcb7e39d4ff1b6` with the unchanged qualified
SDK. It ran from 2026-09-09T20:04:19Z through20:05:45Z and remained **failed**,
as expected. Authorization, canonical builder and explicit preparation passed;
native identify/prepare exited0, then the model integrity gate rejected the
marker. No transcription or complete ASR measurement occurred.

The [raw failure artifact](https://github.com/jiec-msft/foundry-local/actions/runs/34398826339/artifacts/10122627320)
contains a6,034-byte `failure.json`, SHA256
`4c1f6c49793f28076c86753934e6e3c704e992d71e0451768f0ae2d70bdf2d45`.
Its API-reported archive size is1,654 bytes and archive digest is
`8778e6429ef94e6cda71751f65232c3dcb5188aef4a1ca810598f3da49998e43`;
retention is seven days. These are artifact sizes, not network-transfer metrics.
Only metadata was recovered locally, not model files or a new SDK/runtime.

All16 entries were compared against the unchanged SDK model lock, including
every file sorted after the first mismatch. All15 other files match their
exact expected byte counts and SHA256: LICENSE, NOTICES, audio_processor_config,
decoder and encoder ONNX/data, genai_config, joint ONNX/data, model_config,
silero_vad, tokenizer, tokenizer_config and vocab. No additional locked-file
differences were observed.

| Integrity value | Locked Windows inventory | Observed Linux x64 inventory |
|---|---|---|
| Generated marker bytes | 90 | 87 |
| Generated marker SHA256 | `881e9c5b34349dabe826cf88857835d15623c1a92a311d002812c399fe1128ef` | `9bb2dbe6766fb9a5e3e1c8407a88141a480363d0aca7d4df4f88aa3e0399adeb` |
| Sum of16 locked file sizes | 793,344,452 | 793,344,449 |
| Full raw-file manifest SHA256 | `483ce0b37c44b952a369de4257161df7ca42c8621109f20222ad1a9126f55001` | `8d02c1ffd0c9532751ef736ea5941c0733b2219c15ec68c038063dada7e29b8a` |

The actual manifest was independently recomputed from all observed filename,
decimal size and SHA256 entries using the locked ordinal/TAB/LF method.
The marker matches the exact LF candidate, supporting explanation1 on this
Linux x64 run. Different marker fields (explanation2) are not supported by this
digest, and additional differences among the16 locked files (explanation3) are
falsified by the complete inventory. At this diagnostic stage, Linux ARM64 and
macOS ARM64 inventories had not yet been observed; their later observations
are recorded separately below. Their ASR coverage remains absent.

### Proposed portable lock boundary, not implemented

Coordinator/SDK-owner review should distinguish the runtime-generated marker
from the15 immutable payload/configuration/license files, without excluding it
from integrity verification. Keep all common file sizes/hashes unchanged, and
define reviewed **target-specific raw marker bytes/hash, total locked-file size
and complete manifest hash**. Preserve existing Windows x64/ARM64 pins; the
observed Linux x64 tuple above is a proposal for explicit approval, not an
automatically accepted hash. Unobserved targets must remain fail-closed until
their inventory is observed and reviewed.

Verification must still compare actual bytes and the complete target manifest:
no newline normalization, content rewriting, field-only comparison, or accepting
an arbitrary observed digest. No SDK/model-lock, evaluator code, workflow or gate
was changed in this evidence-only continuation. Full-matrix count remains1of2,
plus one diagnostic single-lane dispatch. Further implementation or hosted work
requires a new coordinator decision; prior Windows native evidence and the
first matrix's incomplete artifacts remain separate.

## ARM64 diagnostic inventories

Two separately dispatched diagnostics execute
`b08a704a824fdfaeef33ccd7e670b90d3c404960`, with unchanged SDK source
`d0946a0764d9cfa4b3d684940d6d5c66165427b8` and diagnostic fix
`e7fa302b54fe410d762bd47965fcb7e39d4ff1b6`. Both were created at
2026-09-09T20:28:49Z. Workflow concurrency serialized them; macOS waiting behind
Linux was not a failure, cancellation or native skip.

| Target and run | Native job | Runner image | Completed UTC | Outcome |
|---|---|---|---|---|
| [Linux ARM64,34401279833](https://github.com/jiec-msft/foundry-local/actions/runs/34401279833) | 102633818757 | ubuntu-24.04-arm | 20:30:17Z | Expected marker rejection before ASR |
| [macOS ARM64,34401280998](https://github.com/jiec-msft/foundry-local/actions/runs/34401280998) | 102634290554 | macos-15-arm64 | 20:31:54Z | Expected marker rejection before ASR |

Each run passed authorization, canonical build and explicit preparation. The
executed adapter passed host/JVM/native architecture, native hashes and runtime/
model identity checks before reaching `verify_model`; the checked native targets
were `linux-arm64` and `osx-arm64`. Raw identity-event payloads are not included
in failure artifacts, so they are not presented as separately recovered events.
Each artifact records native identify and prepare exiting0 without timeout or
error events. Each native integration step failed at the expected marker check;
failure staging/upload succeeded. Success-artifact steps were conditionally
skipped, not the native jobs. **Neither run performed transcription or provides
ASR/cancellation/cleanup smoke qualification.**

Both failure artifacts were separately retrieved and compared against all16
entries in the unchanged model lock. Each independently reports the sole
`inference_model.json` mismatch:87 bytes and SHA256
`9bb2dbe6766fb9a5e3e1c8407a88141a480363d0aca7d4df4f88aa3e0399adeb`,
versus the Windows90-byte/`881e9c5b...` pin. All15 other filenames, byte counts
and hashes match, including every file after the marker.

For **each target separately**, summing the observed locked-file sizes gives
793,344,449 bytes. Recomputing the complete ordinal filename/TAB/size/TAB/SHA256/LF
UTF8 manifest gives
`8d02c1ffd0c9532751ef736ea5941c0733b2219c15ec68c038063dada7e29b8a`.
The raw expected/observed per-file inventories remain in the following artifacts.
Their payloads are byte-identical after independent retrieval, not copied from
the Linux x64 evidence.

| Target | Raw failure artifact | API-reported archive SHA256 |
|---|---|---|
| Linux ARM64 | [10123587055](https://github.com/jiec-msft/foundry-local/actions/runs/34401279833/artifacts/10123587055) | `17242805c3ec5dc34a2d21052666dd06b6cc314c37e0b21ca7b21b314238dac4` |
| macOS ARM64 | [10123649414](https://github.com/jiec-msft/foundry-local/actions/runs/34401280998/artifacts/10123649414) | `b312a12a6d10851a2582ae370767f9bf3cdd030f8bb05160c9f0ee7c8d8bc935` |

Each `failure.json` is6,034 bytes with SHA256
`4c1f6c49793f28076c86753934e6e3c704e992d71e0451768f0ae2d70bdf2d45`;
each archive is1,654 API-reported bytes with seven-day retention. These metadata
artifacts contain no model/native payloads. No byte count is relabeled as
measured network transfer.

The marker-only explanation is now supported independently on Linux x64,
Linux ARM64 and macOS ARM64. These additional observations are for the
coordinator to provide to the SDK metadata owner; they do not approve a new pin
or imply a metadata schema. Evaluation integration awaits the actual reviewed
SDK metadata contract. No SDK/model-lock, evaluator code, binary source/hash,
workflow, identity gate or repository policy changed here.

Total budget consumed is **one of at most two full matrices plus three
single-lane diagnostics**. No more dispatches are authorized. The local observer
ran no Java/native/build/model/dependency work; its bounded macOS watcher exited
after discovering completion, leaving no active owned process. Prior Windows
native smoke and all preceding failure artifacts remain separate and unchanged.

## Offline consumer of reviewed metadata38bb

The exact seven-file external SDK metadata commit
`38bbca7f4943687cd90d4aecc365424bb914957e` was scope-reviewed and merged without
conflicts in merge commit `39ce111a25c51a3790b75477d6324ba278e5dd85`. Its SDK
contract files were not edited. All binary-producing source and the legacy
model lock remain at the qualified d094 tuple.

The evaluator now independently pins the metadata revision, validates its actual
schema and invokes its selector from immutable Git blob bytes. It uses verified
native RIDs, checks every raw file plus complete selected manifest/installed
bytes, and emits version3 metadata provenance without changing historical
measurements. The existing source drift, artifact, architecture, runtime,
JVM, licensing, cleanup and budget guards remain in force.

At38bb, both Windows RIDs and Linux x64 pass metadata selection; Linux ARM64 and
macOS ARM64 are still explicitly unobserved and rejected. Later diagnostic
evidence above is not permission to edit or promote the sidecar. Preparation
rejects those targets before downloads; integration rejects before native CLI
inference. Synthetic offline cases do not constitute new native evidence.

No Java, Maven, native inference, model/dependency download or CI dispatch ran in
this consumer continuation. Checked-in dispatch authorization is false.
The next dependency is the coordinator's final reviewed metadata revision,
followed by separately authorized qualification. The remaining full-matrix
budget is one; none of the three diagnostics should be duplicated.

## Final metadata22eb source readiness

The final reviewed metadata revision
`22ebea63b07addb526a1792e0303ba2f572f444a` was merged without conflicts at
`9386ddd9b1ebd34e09bce67407cfbcbeea6d4c2f`. Relative to38bb, only the sidecar,
`MODEL_LOCK.md`, SDK `README.md` and pure metadata tests changed. The schema,
selector implementation, legacy model lock and all binary-producing source
are unchanged. No SDK-owned file was manually edited.

The active evaluator metadata pin now advances to22eb; the binary pin remains
`d0946a0764d9cfa4b3d684940d6d5c66165427b8` and the qualified JAR remains64,000
bytes with SHA256
`bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863`.
Both Windows inventories remain unchanged. The three non-Windows selections
retain their independently observed raw87-byte marker,793,344,449-byte total
and complete manifest
`8d02c1ffd0c9532751ef736ea5941c0733b2219c15ec68c038063dada7e29b8a`.
All16 raw size/hash checks remain mandatory; downloaded bytes are not rewritten
or normalized. Unknown transfer bytes remain null with an explicit reason.

All five actual metadata selections and five synthetic raw-file inventories
pass the focused offline checks. Explicitly simulated unobserved entries still
reject, including preparation before downloads and integration before native
CLI launch. Unknown/native-RID aliases reject. Previous38bb metadata pins,
binary-source drift and metadata-blob drift also reject. Schema and selector
Git-blob equality with38bb is checked independently of the mutable worktree.
The combined existing suite passes69 tests:56 evaluator and13 SDK metadata.

### Hosted schema-tool availability

On2026-09-10, the public image manifests linked by the retained run logs were
inspected for the newly required PowerShell schema validator:

| Standard target | Observed public image version | Included PowerShell | Public image manifest |
|---|---|---|---|
| windows-2022 x64 | 20260907.297.1 | 7.6.5 | [Windows2022](https://github.com/actions/runner-images/blob/win22/20260907.297/images/windows/Windows2022-Readme.md) |
| windows-11-arm ARM64 | 20260830.155.1 | 7.6.4 | [Windows11 ARM64](https://github.com/actions/runner-images/blob/win11-arm64/20260830.155/images/windows/Windows11-Arm64-Readme.md) |
| ubuntu-24.04 x64 | 20260907.300.1 | 7.6.5 | [Ubuntu2404](https://github.com/actions/runner-images/blob/ubuntu24/20260907.300/images/ubuntu/Ubuntu2404-Readme.md) |
| ubuntu-24.04-arm ARM64 | 20260831.111.1 | 7.6.5 | [Ubuntu2404 ARM64](https://github.com/actions/runner-images/blob/ubuntu24-arm64/20260831.111/images/ubuntu/Ubuntu2404-Arm64-Readme.md) |
| macos-15 ARM64 | 20260829.0321.1 | 7.6.4 | [macOS15 ARM64](https://github.com/actions/runner-images/blob/macos-15-arm64/20260829.0321/images/macos/macos-15-arm64-Readme.md) |

Existing public job logs also record actual `pwsh` use on each image.
The official [Test-Json reference](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/test-json?view=powershell-7.6)
documents the built-in `Microsoft.PowerShell.Utility` cmdlet on Windows,
Linux and macOS, its `-Json`/`-Schema` parameters, and JsonSchema.NET validation
since PowerShell7.4. No extra module, installation or CI probe is required.
Hosted image labels can advance; these inspected snapshots establish tool
availability, not execution of the new validator on a future image. The actual
schema check remains mandatory and has no missing-tool fallback.

The checked-in dispatch flag is true under final-source-readiness approval,
not execution permission for this evaluator. All other identity, source/hash,
licensing, explicit-download, cleanup, artifact and budget gates remain intact.
No new Java/Maven/native/model run or hosted dispatch occurred. Historical
Windows smoke stays separate; the three non-Windows targets still need actual
native ASR. The coordinator must review this source before executing the one
remaining full matrix; the three completed diagnostics must not be duplicated.

## Second hosted matrix outcome

[Run34411280765 and its separate evidence report](SECOND_MATRIX_EVALUATION.md)
subsequently completed actual native smoke on all five standard targets.
It executed07e40f0 with metadata22eb and the unchanged d094 JAR, not a later
reporting commit. Each target scored8/151 in both modes and completed early
cancellation/cleanup. The report explicitly records missing success-path raw
per-file inventory exports rather than reusing earlier observations.
The two-full-matrix budget is exhausted; no additional dispatch is authorized.
