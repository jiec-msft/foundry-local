# Historical 06bf Windows Java 17 smoke, 2026-09-10

This is a ten-utterance English **smoke**, not a product quality claim or a
five-platform/JVM compatibility certification.

**Source-specific historical evidence, not current-artifact qualification.**
Subsequent review found Windows non-UTF8 JSONL and a cancel/result-publication
race in 06bf. Qualified source `d0946a0764d9cfa4b3d684940d6d5c66165427b8` addresses
those defects and now has its own [fresh evaluator result](D094_EVALUATION.md).
None of the results or artifact hashes below is relabeled as that source's 64,000-byte JAR
(`bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863`).
The retained 06bf observations and their original hashes are unchanged.

The evaluator ran the immutable public SDK source
`06bf21e65f9a48518a0422558c5bbac42b2fd618` through its own `integration.py`.
The separate SDK worker's previous results were not substituted for this run.
One identity process, ten batch WAV processes, ten paced WAV/PCM processes and
one early cancellation process exited successfully. Every inference result was
followed by `requestClosed`, `modelUnloaded` and `managerClosed`; no inference
child process was reported. All owned JVMs exited, and the compute slot was
released before 01:50:32 +08:00, within the authorized twenty-minute window.

| Observation | Actual result |
|---|---|
| OS / host / JVM / native architecture | Windows / x64 / x64 / x64 |
| JVM | Eclipse Adoptium Temurin 17.0.20.1+1 |
| SDK JAR | 62,370 bytes; Java class major version 61 throughout |
| JNA | 5.17.0, separate 2,002,589-byte JAR |
| Runtime | 2.0.1, packaged API 1 header and per-library hashes |
| Exact model | nemotron-3.5-asr-streaming-0.6b-generic-cpu:3, CPUExecutionProvider |
| Corpus | 10 full utterances, 60.28 seconds, 151 reference words |
| Batch WAV WER | 8 / 151 = 5.298%; 5 substitutions, 0 deletions, 3 insertions |
| Paced WER | 8 / 151 = 5.298%; 5 substitutions, 0 deletions, 3 insertions |
| Clean / other | 3 / 62 (4.839%) / 5 / 89 (5.618%) in each mode |
| Paced first meaningful result | 1253.391-2413.696 ms after native input admission |
| Paced natural-close to finalization | 172.193-324.152 ms |
| Paced RTF | 1.0178-1.0802, includes deliberate pacing waits |
| Cancellation request / acknowledgment | 1237.381 / 1321.631 ms, request-local clock |
| Cancellation acknowledgment latency | 84.250 ms; 39,040 PCM bytes admitted; natural input close null |
| Peak root JVM RSS observed | 1,060,405,248 bytes, OS peak working set sampled at 100 ms |
| Model installed files | 793,344,452 bytes, exact model-lock content hashes |
| Prepared runtime installed files | 35,772,965 bytes |
| Native model-load durations | 2079-2895 ms; distinct from end-to-end readiness |

End-to-end readiness and actual runtime/model/artifact network transfer bytes
remain **unknown with explicit reasons** in measurement version 2. Installed
file sizes are not download measurements. The populated exact model cache and
verified public SDK/runtime/JDK artifacts were reused; no duplicate runtime/model
download was requested. Public catalog API 1 can still network, so this is not
strict offline proof.
The readiness `cold_start: false` field describes the populated model cache,
not a reused JVM: all 22 commands started fresh JVM processes.

The SDK's native TOKEN events are text deltas. They are preserved as received;
final aggregate native results, not a token-concatenation fallback, supply scored
hypotheses. Each `result.timing` has its own request-local monotonic origin.
Input admission, first nonblank callback, natural close, terminal response,
cancellation request, and subsequent cleanup are separate observations.

## Artifacts and reproducibility

Small structured artifacts remain in the ignored run output directory,
`build/windows-java17-run2/`, for the coordinator's review/publication. They total
203,245 bytes and contain no machine-specific paths. Raw per-process stdout,
stderr, failure diagnostics and application data remain local under that output,
not in the allowlisted public artifacts. Models, runtime binaries, corpora and
JDKs are not included.

| Artifact | SHA256 |
|---|---|
| report.json | `696a7b0a21b8c978ac7332c78d531f1a15c10ec450138a0a143ff2da569bcc66` |
| measurement.json | `72d11c3dcf6558f61f08db60c03171b2d394d21e0464ae9eae0b4607cc243255` |
| events.jsonl | `5ac030454b60a7a4dab01f83613296e0310bd6628eed3c5c057e3fbbb3d2416d` |
| platform.json | `776d6e0d74512d87ae7e065785dda0ca7028f61802542b8cb16b8f49c14e21ca` |
| SDK JAR | `d9620c6a40199f1bc8359c91dad4d07e3dc5b3f959a2ad6b3029e8053a45bbcf` |
| JNA JAR | `b3a9408e7c51e08ef0e3bfcc08f443f6ec0f6191ba8cd7c18d53d2b22e5bdbc0` |

The first identity-only attempt exposed an evaluator mismatch between
`java.version` and the SDK's `java.runtime.version`; it was corrected without SDK
changes. The full native batch then completed, while its original scorer process
still held the previous measurement-v1 code. Report finalization consequently
failed after all native commands had finished. The revised version-2 scorer was
run against the retained actual measurement/process evidence using
`finalize_evidence.py --output build/windows-java17-run2`; it cross-checks every
authoritative transcript, timestamp, cancellation and cleanup event. No native
inference was rerun to repair postprocessing. Both original failures remain in
local diagnostics; this is not an assertion that the first command succeeded.

## Limits and next CI gate

Only the actual Windows Java 17 lane is evaluator-owned evidence here. The
separately authorized SDK evidence on official IU 2026.1.5/JBR 25 is not a second
full evaluator measurement. JBR 21.0.8/21.0.9 with app-local CRT 14.29 remain
incompatible, not all Java 21. The universal minimum compatible CRT/JBR is unknown;
see the SDK's [Windows loading notes](../WINDOWS_LOADING.md).

Model redistribution is not authorized. The public model card, catalog license
description and packaged notices differ; see the SDK's documented license
discrepancy. Do not turn local use into blanket redistribution permission.

Actions remains disabled, dispatch authorization false, and hosted execution count
zero. No workflow was registered on default main and no PR/release/settings change
was made. Coordinator review, safe default-branch workflow registration, narrow
allowlisting and explicit dispatch authorization are required before hosted work.

The hosted workflow uses a standard Windows x64 canonical build, not a Linux
rebuild of the fixed Windows artifact: inspection found CRLF native-lock
resources and Maven properties in the supplied JAR. It verifies the original
JAR hash rather than repackaging a different artifact. All native hosted lanes,
including native Microsoft JDK17 on Windows ARM64, remain unexecuted.
