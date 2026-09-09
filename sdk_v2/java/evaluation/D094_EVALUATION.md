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

## Remaining coordinator gates

All five standard native JDK17 hosted lanes remain unrun. The coordinator has
approved source-side readiness and operational evaluation-use licensing for the
first bounded public matrix. The three readiness flags are true; source refresh
remains cleared. Repository Actions is still disabled and no run was dispatched.
The old06bf evidence remains separate. Model/native redistribution and production
deployment are not authorized. The catalog/card/packaged-notice discrepancy is
preserved rather than relabeled as all-MIT weights; exact scope and reviewed
public sources are recorded in `model.license_review` in `ci-lock.json`.

The sole hosted allowlist is `java-sdk-evaluation.yml`; the unapproved automatic
unit workflow is removed while all offline tests remain. The coordinator alone
handles default-main configuration, workflow registration, narrow activation
and the first dispatch. No inherited workflow, default-branch, repository setting,
issue, PR, release or dispatch mutation was made here. The approved first-matrix
inputs, for coordinator execution after activation, are:

```powershell
gh workflow run java-sdk-evaluation.yml --repo jiec-msft/foundry-local `
  --ref mason/java-asr-evaluation `
  -f sdk_sha=d0946a0764d9cfa4b3d684940d6d5c66165427b8 -f lane=full-matrix
```

At most two full matrices are allowed, with max-parallel2 and20 minutes per job.
A failed-lane dispatch requires its exact `lane`, prior `failed_run_id`, reviewed
descendant `fix_sha`, and concrete `fix_reason`; whole-run retries are rejected.
No new local inference is requested by this handoff.
