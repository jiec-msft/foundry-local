# Second and final standard hosted matrix

[Run34411280765](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765)
completed successfully from2026-09-09T22:15:21Z to22:26:06Z.
**All five targets completed actual native ASR smoke**, not just preparation:
ten fixed WAVs, ten paced streams and one early cancellation per target.
The same ten public LibriSpeech utterances contain151 reference words and60.28s
of audio; they are smoke evidence, never a product-quality benchmark.

**Evidence limitation:** success artifacts do not include
`model-verification.json`. The exact executed integration requires all16 actual
raw file sizes/hashes, the complete ordinal manifest and installed-byte total to
match before any transcription. The retained v3 provenance and actual installed
totals match the selected contract, whose complete expected inventory was
independently recomputed. However, the new observed per-file rows and an
independent recomputation from those rows are unavailable. No earlier diagnostic
inventory is relabeled as evidence from this run. No implementation or upload
allowlist was changed to hide or remedy this reporting limitation.

## Immutable identities

| Identity | Exact value |
|---|---|
| Workflow/event/attempt | 354315764 / `workflow_dispatch` /1 |
| Executed evaluation source | `07e40f066997d326c189f492225bc5a7bb193c0a` |
| Metadata source | `22ebea63b07addb526a1792e0303ba2f572f444a` |
| Binary SDK source | `d0946a0764d9cfa4b3d684940d6d5c66165427b8` |
| Thin SDK JAR | 64,000 bytes; `bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863` |
| JNA5.17.0 | `b3a9408e7c51e08ef0e3bfcc08f443f6ec0f6191ba8cd7c18d53d2b22e5bdbc0` |
| Runtime | Microsoft.AI.Foundry.Local.Runtime2.0.1, packaged API1 |
| Runtime package SHA256 | `f509b4509f3fd452bfe9dd0721feabc407689b9d105da71c63e5a2f87bd9f03c` |
| ORT / GenAI.Foundry | 1.28.0 /0.15.2 |
| Exact model/provider | `nemotron-3.5-asr-streaming-0.6b-generic-cpu:3` / `CPUExecutionProvider` |
| Sidecar Git-blob SHA256 | `6cf1789a5f72fd46ca8afd360730735f00e978398f32e38056d795b3154055d2` |
| Schema Git-blob SHA256 | `b1c60a3516eacd1c9dcbce6b9fdf85d0b208993c69d65c1f8093510d5d5723d2` |
| Selector Git-blob SHA256 | `d4db9985b2e8b65a0c9a48c1c944eceb36871ba0d03b8ada4048551c1d221f61` |

The canonical builder and authorization jobs passed. The downloaded JAR has the
qualified hash,27 Java17 classes and no bundled native/model libraries. Every
lane's native-library hashes match its exact SDK `native-lock.properties` RID
entries. Each of its23 runtime handshakes agrees with its measured JVM,
native RID, runtime version and API1. This executed source remains distinct
from the later documentation-only reporting commit.

## Separate platform outcomes

| Target / actual native RID | Job ID | Standard runner / actual image version | Host/JVM/native arch | Actual JDK17 vendor/version | Native smoke |
|---|---|---|---|---|---|
| Windows x64 / `win-x64` | 102666286611 | windows-2022 /20260907.297.1 | x64/x64/x64 | Eclipse Adoptium17.0.20.1+1 | PASS |
| Windows ARM64 / `win-arm64` | 102666286553 | windows-11-arm /20260830.155.1 | arm64/arm64/arm64 | Microsoft17.0.20.1+1-LTS | PASS |
| Linux x64 / `linux-x64` | 102666286533 | ubuntu-24.04 /20260907.300.1 | x64/x64/x64 | Eclipse Adoptium17.0.20.1+1 | PASS |
| Linux ARM64 / `linux-arm64` | 102666286609 | ubuntu-24.04-arm /20260907.118.1 | arm64/arm64/arm64 | Eclipse Adoptium17.0.20.1+1 | PASS |
| macOS ARM64 / `osx-arm64` | 102666286693 | macos-15 /20260829.0321.1 | arm64/arm64/arm64 | Eclipse Adoptium17.0.20.1+1 | PASS |

No native lane, preparation or inference step was skipped, failed, timed out or
cancelled. The only skipped steps were the two conditional failure-export steps
in each successful lane. Unsupported macOS x64 remains outside the matrix;
an ARM64 result does not establish a particular Apple chip, plugin or microphone
integration. CPU model/core count were not captured. These are different hosted
machines, OS images and, for Windows ARM64, a different JDK distribution, not
a controlled hardware comparison.

Each lane contains23 **process-wrapper rows**, not23 SDK events. Nested
`events[]` prove ten non-cancelled `transcribe` results, ten non-cancelled
`stream` results and one cancelled `stream` result. Every inference has one
ordered result/requestClosed/modelUnloaded/managerClosed sequence, zero
result-time child processes and process exit0. Identify and prepare also exit0,
but their early-return path has no managerClosed event; that absence is not
invented into cleanup evidence.

There are115 wrappers and6,763 schema-valid nested SDK event objects in total:
1,353 per target except macOS with1,351. The105 inference results have105 complete
cleanup sequences. Event counts were derived from their actual shape, not assumed
from line counts or run labels.

## Selected inventory and retained integrity evidence

| Targets | Selected raw marker bytes | Selected marker SHA256 | Actual installed bytes recorded | Complete selected manifest SHA256 |
|---|---|---|---|---|
| Windows x64 and ARM64, checked separately | 90 CRLF | `881e9c5b34349dabe826cf88857835d15623c1a92a311d002812c399fe1128ef` | 793,344,452 each | `483ce0b37c44b952a369de4257161df7ca42c8621109f20222ad1a9126f55001` |
| Linux x64, Linux ARM64 and macOS ARM64, checked separately | 87 LF | `9bb2dbe6766fb9a5e3e1c8407a88141a480363d0aca7d4df4f88aa3e0399adeb` | 793,344,449 each | `8d02c1ffd0c9532751ef736ea5941c0733b2219c15ec68c038063dada7e29b8a` |

All15 common expected payload/configuration/license entries retain their exact
base-lock sizes/hashes. All five v3 measurements separately bind the correct
RID, metadata revision, three metadata source-blob hashes, selected manifest
and actual installed total. Manifest records use ordinal filename sorting and
UTF8 `filename<TAB>decimal bytes<TAB>SHA256<LF>`. The raw success-inventory export
limitation above applies to every lane; these selected tuples are not fabricated
observed rows. No content was normalized or accepted by an observed-hash fallback.

## WER and request-local measurements

| Target | WAV edits/reference words | Paced edits/reference words | Clean, each mode | Other, each mode |
|---|---|---|---|---|
| Windows x64 | 8/151 | 8/151 | 3/62 | 5/89 |
| Windows ARM64 | 8/151 | 8/151 | 3/62 | 5/89 |
| Linux x64 | 8/151 | 8/151 | 3/62 | 5/89 |
| Linux ARM64 | 8/151 | 8/151 | 3/62 | 5/89 |
| macOS ARM64 | 8/151 | 8/151 | 3/62 | 5/89 |

Every corpus result is5 substitutions,0 deletions and3 insertions:
WER8/151 =5.298%. Clean has1 substitution and2 insertions; other has4
substitutions and1 insertion. The independent scorer reproduced all raw and
normalized text, per-sample counts, subset totals, timing fields and measurement
content. Hosted Python Unicode database versions differ:15.0.0 on Windows x64
and Linux,15.1.0 on Windows ARM64,16.0.0 on macOS; observer14.0.0. Those provenance
values are preserved, not rewritten to make whole-report equality appear exact.

The following are minimum-maximum ranges over the same ten requests, rounded
to three decimals. They are **not p95, product latency or cross-model results**.
First nonempty subtracts first admitted input from request-local first nonempty;
finalization subtracts input-close from finalized. RTF divides first-input-to-final
wall time by audio duration. No CLI-global `elapsedMillis` is mixed into them.

| Target | Paced first nonempty ms | Paced finalization ms | Paced RTF | WAV first nonempty ms | WAV finalization ms | WAV RTF |
|---|---|---|---|---|---|---|
| Windows x64 | 1265.882-2378.700 | 167.161-248.385 | 1.017-1.055 | 439.112-778.839 | 678.230-858.008 | 0.328-0.370 |
| Windows ARM64 | 1273.926-2406.847 | 183.809-259.385 | 1.019-1.061 | 454.222-842.836 | 744.928-941.368 | 0.354-0.392 |
| Linux x64 | 1260.222-2381.965 | 168.692-250.883 | 1.018-1.057 | 363.599-721.004 | 715.591-924.039 | 0.321-0.369 |
| Linux ARM64 | 1237.395-2355.634 | 144.482-194.798 | 1.015-1.044 | 311.297-600.088 | 593.190-745.900 | 0.273-0.305 |
| macOS ARM64 | 1313.865-2533.781 | 226.714-522.701 | 1.038-1.116 | 529.899-1001.151 | 940.218-1360.288 | 0.454-0.595 |

| Target | Cancellation requested/finalized ms | Acknowledgment delta ms | Admitted PCM bytes | Root JVM RSS bytes | Installed runtime bytes |
|---|---|---|---|---|---|
| Windows x64 | 1234.909/1299.763 | 64.854 | 39,040 | 1,040,883,712 | 35,772,965 |
| Windows ARM64 | 1236.738/1301.732 | 64.993 | 39,040 | 1,013,121,024 | 38,637,109 |
| Linux x64 | 1229.122/1300.985 | 71.863 | 39,040 | 1,059,328,000 | 106,582,317 |
| Linux ARM64 | 1221.105/1264.258 | 43.153 | 38,400 | 1,018,228,736 | 98,844,685 |
| macOS ARM64 | 1231.336/1379.016 | 147.680 | 39,040 | 1,020,477,440 | 104,782,645 |

Cancellation is one early request per target, not a distribution. Every
cancelled result has empty final text, `cancelled=true`, no natural input-close,
nativeFinishReason0, explicit cleanup and exit0. Cancellation is established
by these fields, not by misinterpreting the native reason integer.

RSS is the maximum recorded across the23 root JVM processes. Windows samples
OS peak working set and Linux samples VmHWM at approximately100ms intervals;
macOS samples current RSS and therefore reports a **lower bound**, not an OS
high-water mark or whole-system memory. Exact unrounded metrics remain in the
measurement/report artifacts. End-to-end readiness and runtime/model/artifact
network-transfer values remain null with explicit reasons. Installed byte
counts and native download percentages are not substituted for transfer bytes.

## Small retained artifacts

All six downloaded ZIP payload hashes and lengths match the GitHub API receipts.
The total is180,643 archive bytes and1,196,790 extracted bytes, below50MB.
Each native artifact contains only measurement, report, platform, nested events
and their `SHA256SUMS.json`; every internal size/hash was also checked.
The builder artifact contains only the thin JAR. No model/native/runtime/corpus
payload was downloaded by the observer or uploaded as an artifact.

| Artifact link | ZIP bytes | ZIP SHA256 | Extracted bytes |
|---|---|---|---|
| [Windows x64](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127451632) | 24,182 | `4bb2bb2137f02a5eb8324ded069eeb330a606548237ac2b0cf836dab5f595996` | 226,947 |
| [Windows ARM64](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127448980) | 23,879 | `ec29dd8e86c14fca0bf5f247043b033aac4c51ea4b6fecdd0d91189261a04fc7` | 227,107 |
| [Linux x64](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127544789) | 24,334 | `ee1ad58cbd8734aa18809f31eecbba8e95f5229c301a9a66cbe0f6b7accfe152` | 226,379 |
| [Linux ARM64](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127535699) | 24,236 | `5e1bbffd5c96cb6426030f0140b5aacfbb894a195b46cbbefd260f1bb1d5eeeb` | 226,334 |
| [macOS ARM64](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127655814) | 24,487 | `3a27a23347233b3527f8697d439c5a3bcae475d3288bba1a3e199b115856c0cd` | 226,023 |
| [Qualified thin JAR](https://github.com/jiec-msft/foundry-local/actions/runs/34411280765/artifacts/10127340452) | 59,525 | `cbd985e73e4df9f8e00dc4d11c9850484f0783683b60a5f4f463cb322a98f429` | 64,000 |

Artifacts expire on2026-09-16, seven days after upload. Archive payload lengths
are not SDK network-transfer telemetry. The local offline validation report is
190,006 bytes, SHA256
`d8147df6d6bd81699b3e3f1b8a098588d8076020ff6609c2d48ef7fba8ed935d`;
it retains per-target exact metrics, all selected file tuples, job/step
conclusions and complete downloaded-file inventories.

The single local watcher ran22:19:19.635120Z-22:26:35.181487Z with60-second
intervals and exited0, well inside its one-hour bound. No watcher/native process
remains. No local Java/Maven/native/model execution or new dependency was used.

Both full matrices are now consumed: **2/2 full matrices plus3 diagnostics,
five unique runs total**. No further full matrix, rerun or failed-lane dispatch
is authorized. No source/pin, repository policy, default branch, release or
production publication changed. Evaluation-only license approval and the
catalog/card/packaged-notice discrepancy remain; neither all-weights-MIT nor
model/native redistribution, UI/plugin or microphone completion is claimed.
