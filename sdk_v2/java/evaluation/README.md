# Public Java ASR smoke evaluation

**Qualified d094 Windows Java17 refresh complete; hosted CI remains disabled and undispatched.**
This directory is independently authored evaluation code, not an SDK implementation.
The ten fixed English utterances are a smoke set, **never a product quality claim**.
They are not representative of languages, accents, microphones, conversational speech,
long recordings, accessibility needs, or the population of users.

The active SDK source is `d0946a0764d9cfa4b3d684940d6d5c66165427b8`,
with a qualified 64,000-byte JAR whose SHA256 is
`bf644d3127afff912683731094821a8f6a751f003c284a9c15ddceaecebe0863`.
The evaluator installed a verified, read-only source/hash-scoped SDK/JNA copy
before running the existing ten batch WAVs, ten paced20ms streams and cancellation
once. All22 native CLI processes exited0 with complete inference cleanup;955
events passed strictUTF8 and the SDK event schema. Both modes produced
**8 edits / 151 reference words (5.298% WER)** from fresh d094 output. An isolated
offline Windows build also reproduced the exact JAR hash without overwriting it.
See [D094_EVALUATION.md](D094_EVALUATION.md) for timings, hashes and limits.

The separate [historical06bf evidence](LOCAL_EVALUATION.md) is unchanged and is
not relabeled as new-artifact qualification. The d094 source fixes its Windows
JSONL encoding and cancel/result-publication defects. The source-refresh gate is
cleared after qualified installation. Source-side readiness is approved for the
first bounded matrix; repository Actions activation and dispatch remain coordinator-only.

## Frozen public fixtures

Source: [OpenSLR SLR12 / LibriSpeech](https://www.openslr.org/12), development
`dev-clean` and `dev-other` only. The corpus was prepared by Vassil Panayotov with
the assistance of Daniel Povey, from LibriVox read audiobooks. Please attribute:

> LibriSpeech (c) 2014 Vassil Panayotov. Vassil Panayotov, Guoguo Chen, Daniel
> Povey and Sanjeev Khudanpur, "LibriSpeech: an ASR corpus based on public domain
> audio books", ICASSP 2015. Audio read by the LibriVox readers represented by
> the public speaker IDs below.

Audio and reference transcripts remain **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**,
not MIT. Preserve this attribution and `fixtures/LICENSE.TXT` when redistributing.
That license permits the small attributed fixture subset to be committed. The
only transformation is lossless FLAC decoding to canonical PCM WAV; the complete
corpus utterances are retained, not clipped, re-recorded, resampled, denoised,
silence-trimmed, or collected from a human for this POC. No endorsement is implied.
Evaluation code is MIT; see `LICENSE`.

Selection was fixed **before any recognition**: within each subset, sort
`(speaker, chapter, utterance)` numerically; choose the first complete 4-10-second
utterance of each of the first five eligible distinct speakers. No transcripts,
recognition results, model outputs, or manual listening influence selection.
The corpus's own utterance boundaries need not coincide with whole sentences.
Clean/other is balanced by sample count, not by seconds or words.

| Subset | Utterance / public speaker ID prefix | Seconds |
|---|---|---:|
| dev-clean | 84-121123-0003 | 6.800 |
| dev-clean | 174-50561-0000 | 4.020 |
| dev-clean | 251-118436-0000 | 6.260 |
| dev-clean | 422-122949-0002 | 4.475 |
| dev-clean | 652-129742-0000 | 6.025 |
| dev-other | 116-288045-0001 | 8.635 |
| dev-other | 700-122866-0000 | 4.890 |
| dev-other | 1255-74899-0002 | 4.850 |
| dev-other | 1585-131718-0002 | 9.715 |
| dev-other | 1630-73710-0001 | 4.610 |

`manifest.json` is the frozen ID/reference/provenance authority. It records archive
URLs, OpenSLR's published MD5s and locally computed SHA256s, source FLAC and
transcript member hashes, decoder/package versions and wheel hashes, frame counts,
WAV/PCM hashes, and unchanged raw reference transcripts. All WAVs are mono
16000 Hz signed PCM16 little-endian with a canonical 44-byte WAV header.
The ten files total 1,929,400 bytes and 60.28 seconds.

## Offline checks and reproducibility

Independent scoring needs only Python 3.11+ stdlib and the committed WAVs.
Target-metadata consumers/tests additionally use existing Git and PowerShell7
`Test-Json` for immutable source and JSON Schema2020-12 validation. No model,
runtime, native build, corpus download, decoder, or account is needed:

```powershell
python -m unittest discover -s sdk_v2\java\evaluation -p "test_*.py" -v
```

To reproduce the frozen fixture bytes on Windows x64 CPython 3.11, install the
hash-pinned public preparation wheels in an ignored build directory. These are
preparation dependencies only, never dependencies of the Java SDK or scorer:

```powershell
New-Item -ItemType Directory -Force sdk_v2\java\evaluation\build | Out-Null
python -m pip install --index-url https://pypi.org/simple --only-binary=:all: --require-hashes `
  --target sdk_v2\java\evaluation\build\decoder `
  --report sdk_v2\java\evaluation\build\decoder-install.json `
  -r sdk_v2\java\evaluation\prepare-requirements.txt
$env:PYTHONPATH = (Resolve-Path sdk_v2\java\evaluation\build\decoder).Path
python sdk_v2\java\evaluation\prepare_fixtures.py `
  --cache sdk_v2\java\evaluation\build\corpus-cache `
  --output sdk_v2\java\evaluation\build\reproduced `
  --decoder-report sdk_v2\java\evaluation\build\decoder-install.json
```

Reuse the existing explicit cache path; do not duplicate caches. The two development
archives total 652,232,214 bytes, are downloaded once if absent, and are never committed
or uploaded. A mismatching cached hash or interrupted partial download fails explicitly;
inspect it rather than silently replacing it. Reproduction checks against frozen archive
SHA256s and compares every reproduced sample field and WAV hash to the manifest.
`--initial-curation` is only the one-time pre-recognition freeze mechanism, not permission
to reselect fixtures after observing model output. A changed set requires a new version.

## Scoring and evidence

`scorer.py` implements deterministic word-level Levenshtein edit counting independently.
Normalization uses Unicode NFKC and casefold, canonical internal apostrophes,
punctuation-to-word-boundaries and collapsed whitespace. It does **not** expand
numbers, rewrite spellings, remove filler words, or choose alternate references.
The module documents exact apostrophe and tie-breaking behavior; golden tests
fix it. Reports also record the Python Unicode database version used by
normalization. The score is:

```text
corpus WER = sum(substitutions + deletions + insertions) / sum(reference words)
```

Do not average per-utterance WERs. Report pooled corpus, `dev-clean`, and
`dev-other` counts and WERs, plus each utterance's raw and normalized reference
and hypothesis. Zero-reference WER is undefined (`null`), not zero. A missing
hypothesis is invalid evidence; an actual empty hypothesis is scored as deletions.

New target-aware output uses `measurement.schema.json` version3. It preserves
unknown metrics as `{"value": null, "reason": "..."}` rather than inventing
zeros or equating installed size with network transfer. The scorer still accepts
historical version2 measurements and version1 golden fixtures without relabeling
them. Version3 separately records `sdk.metadata_git_sha` and
`provenance.model_inventory`: verified native RID, selected manifest, actual
installed bytes and SHA256 of the three consumed metadata Git blobs. Scoring
requires agreement with model hash, resource bytes and actual architecture.
After authorized actual SDK execution:

```powershell
python sdk_v2\java\evaluation\scorer.py `
  --manifest sdk_v2\java\evaluation\manifest.json `
  --measurement sdk_v2\java\evaluation\build\results\measurement.json `
  --output sdk_v2\java\evaluation\build\results\report.json
```

Retain original SDK JSONL as `events.jsonl` (including batch and streaming output)
and the complete raw measurement in the scored report. Never substitute fixture
references, example transcripts, unit-test synthetic data, or generated timing
values for recognition evidence.

Measurement semantics for `integration.py`:

- Record SDK commit, runtime version and package SHA256, exact model ID/version/hash,
  JDK version/vendor, OS, and actual host/JVM/native architecture, not just runner labels.
- End-to-end readiness is unknown because the CLI does not expose a single
  observation covering it. Actual model-load durations are retained separately;
  existing-cache state is recorded. Neither is first-token latency.
- Feed 20 ms PCM chunks against monotonic deadlines at the original 16000 Hz rate;
  record the actual chunk duration (up to 100 ms is accepted, never a whole-file
  burst disguised as streaming). Timing timestamps are milliseconds from one
  request-local monotonic origin from `result.timing`. Never mix these with
  `speech.elapsedMillis` (a different CLI origin). `feed_started_ms` is first admitted audio;
  `input_closed_ms` is end-of-input submission; `finalized_ms` is final-result receipt.
- First-nonempty latency is first nonempty hypothesis time minus first audio submission;
  if no nonempty output exists, preserve `null`, never zero. Finalization latency is
  final-result receipt minus end-of-input. Record whether partial output only arrives
  at finalization; do not claim live partial support if it does not exist.
- `inference_wall_ms` covers first submitted audio through final result, including
  pacing, but excluding readiness. RTF is that duration divided by source audio
  duration; **paced RTF includes deliberate waiting**, not pure compute throughput.
- Peak RSS is bytes for the inference JVM process (include child/native processes if
  any, with the method/scope explicit in `rss_method`), not this Python scorer's RSS.
  Download byte counts mean actual network payload bytes, not cache size or installed
  size. Runtime and model installed bytes are separate; cold and cached runs must be
  distinguished. A real warm-cache zero is allowed; unknown values cannot become zero.
- Lifecycle success requires actual native loading, cancel acknowledgment/termination,
  and released sessions/queues/files with no surviving child process. Missing evidence
  is an incomplete run, not a success-shaped default.

The adapter executes `transcribe --wav` and then paced `stream --wav` for each of
the ten committed WAVs, followed by a cancellation/cleanup probe. Both modes are
scored independently against the same frozen references. TOKEN text is delta
evidence, not revisable partial text; the final aggregate result is authoritative.
`requestClosed`, `modelUnloaded`, `managerClosed`, zero child-process count and
exit 0 are required for inference. The SDK's identify/prepare early-return paths
emit no `managerClosed`; their process exit is recorded without claiming that marker.

## Fixed SDK dependency and ABI

`sdk-contract.json` records the public runtime tuple supplied by the coordinator:
`Microsoft.AI.Foundry.Local.Runtime 2.0.1`, ORT `1.28.0`, and
`Microsoft.ML.OnnxRuntimeGenAI.Foundry 0.15.2`; Java 17 with JNA.
The runtime package and its own C header are SHA256-pinned in that file.
**Use the package's own API_VERSION=1 header.** Public main and the `v2.0.1`
tag header have API_VERSION=2 and must not be used with that packaged binary.
Actual runtime identity, native file hashes and model content hashes were verified
before the evaluator's own Windows run.

Bound CLI: `identify`, `prepare --explicit-download --accept-model-license`, `transcribe --wav`,
`stream --wav` (paced PCM) or `--pcm`, optional `--cancel-after-ms`, with
explicit `--runtime-dir`/`--cache-dir`/`--app-data-dir` and JSON-lines stdout.
The actual SDK [API](../API.md), [event schema](../cli.schema.json), model lock
and bundled runtime/native locks are authoritative. SDK API/build changes belong
to the coordinator/SDK worker, not this directory.

## Independently pinned target metadata

The reviewed external SDK contract is merged at
`22ebea63b07addb526a1792e0303ba2f572f444a` and pinned separately as
`metadata_git_sha` in both CI locks and `model_inventory.py`. Binary source
remains `d0946a0764d9cfa4b3d684940d6d5c66165427b8`; its64,000-byte JAR hash,
Java17 bytecode, legacy `model-lock.json` and complete existing binary-source
drift check remain unchanged.

`model_inventory.py` rejects drift against the two revisions separately, then
reads the base lock from the binary revision and the sidecar/schema/selector
directly from the metadata revision's Git blobs. The SDK selector executes those
verified source bytes, not a mutable working-tree module or cached bytecode.
Thus a matching `metadata_git_sha` string in JSON is not sufficient provenance.
The actual SDK schema is enforced with existing `Test-Json`; no packages are
downloaded to validate it.

Preparation preflights the RID derived from verified native host identity before
downloads, then selects again after actual JVM/native verification. Integration
selects using the verified native RID returned by `verify_artifacts`, never a
lane alias. It invokes the SDK's `select_model_inventory` without duplicating
its selection rules. All16 actual files, including the raw generated marker,
must match selected sizes/hashes, complete ordinal manifest and total bytes.
Failure evidence retains those comparisons, RID and metadata revision.

At the pinned22eb revision, all five exact RIDs are observed: `win-x64`,
`win-arm64`, `linux-x64`, `linux-arm64` and `osx-arm64`. The two Windows
inventories remain byte-for-byte equivalent to the legacy base lock. Each
non-Windows inventory uses its separately observed87-byte LF marker,
793,344,449-byte total and complete `8d02c1ff...` manifest. Only the SDK owner
updates that contract; no evaluator fallback or automatic promotion is
permitted. Unknown RIDs and simulated unobserved entries still reject before
downloads or inference. **Inventory readiness is not native ASR qualification.**

## First hosted matrix and final source readiness

The sole approved hosted workflow is `java-sdk-evaluation.yml`; model evaluation is
**workflow_dispatch only**, owner/repository/ref guarded, and fails closed against
`ci-lock.json`. Its integration entry point invokes the real bounded evaluator
after explicit pinned preparation. Neither that gate nor parsing native headers
is evidence that an ASR model ran on a hosted target. The automatic
`java-sdk-unit.yml` workflow is removed from this branch; all offline tests and
the documented `python -m unittest discover` command remain available.

The checked-in `enabled`, `dispatch_authorized` and
`dependency_license_review_complete` flags are **true** for the reviewed final
source preparation. `source_pin_refresh_required` remains false. This permits
coordinator review of source eligible for the one remaining standard full matrix;
it neither executes a run nor authorizes this evaluator to dispatch.
Repository operations remain with the coordinator. The sole workflow allowlist
is `java-sdk-evaluation.yml`; inherited workflow configuration is unchanged here.

Standard labels were rechecked against the public
[GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
on 2026-09-09:

| Lane | Standard runner | Actual required architecture |
|---|---|---|
| Windows x64 | windows-2022 | x64 |
| Windows ARM64 | windows-11-arm | arm64 |
| Linux x64 | ubuntu-24.04 | x64 |
| Linux ARM64 | ubuntu-24.04-arm | arm64 |
| macOS ARM64 | macos-15 | arm64 |

The exact public image manifests used by the completed runs list PowerShell
7.6.4 or7.6.5 on all five targets, including Linux ARM64 and macOS ARM64.
`Test-Json -Json ... -Schema ...` is a built-in cross-platform cmdlet; metadata
validation installs no module and fails closed if the tool is unavailable.
See [the per-image sources and limitations](D094_EVALUATION.md#final-metadata22eb-source-readiness).

All five lanes have explicitly pinned **native JDK 17** downloads. Temurin 17
has no Windows ARM64 artifact, but Microsoft publishes a native Windows ARM64
17.0.20.1 archive; its public checksum and size are pinned in `ci-tools-lock.json`.
No emulation or silent native-test skip substitutes for that lane.

One standard Windows x64 job builds the canonical SDK with pinned Temurin 17
and Maven, then shares only the 64,000-byte, exact-hash-verified thin JAR.
The original artifact contains CRLF resources and Maven properties; a Linux
rebuild would change its bytes. The canonical Windows checkout therefore uses
explicit CRLF text handling rather than modifying SDK source/resources or
accepting a different JAR hash. Every native lane rechecks Java17 bytecode and
JAR/JNA hashes. The isolated local offline rebuild reproduced the qualified bytes;
the first hosted builder also reproduced them. In
[run34396100361](https://github.com/jiec-msft/foundry-local/actions/runs/34396100361),
Windows x64 and ARM64 completed actual native smoke. Linux x64/ARM64 and macOS
ARM64 failed model-cache integrity verification before ASR; they are not qualified.
See [the separate hosted evidence section](D094_EVALUATION.md#first-hosted-matrix).

`platform_checks.py` compares actual host (including emulated-process cases),
JVM properties and individual PE/ELF/Mach-O native machine headers. The adapter
must also observe the actual native-loaded lifecycle event and verify **all**
runtime/ORT/GenAI shared libraries that it uses. macOS x64 is an explicit
unsupported-path unit test, not an invented ASR lane. Request the corresponding
SDK unsupported-path test through the coordinator.

Budget rules are committed: local Windows success first, explicit dispatch permission,
two full matrices maximum, max-parallel 2, timeout 20 minutes/model job, and no
paid/larger/GPU/self-hosted runners or `pull_request_target`. Prior full-matrix
dispatches are counted conservatively, even failed/cancelled ones; automatic
whole-run retries are rejected. Single-lane dispatches require a concrete reviewed
fix commit and explanation; the coordinator must confirm that the lane failed.
Do not delete run history to reset the budget. Stop/review after two full matrices.

Artifact staging allowlists only report/measurement/JSONL/platform/JAR files,
rejects bundled natives/models, and caps each lane at 9,000,000 uncompressed bytes
(five lanes under 50 MB/run, including inventories). Retention is seven days.
There is no Actions cache; corpus archives, models and full runtimes must not be
uploaded. Any later cache requires license review and a total below 10 GB.
Failed model verification now retains only expected/observed file sizes and SHA256
values, plus manifest digests, in bounded `failure.json`. It never uploads model
contents or normalizes a mismatched file into acceptance.
Do not enable inherited workflows. Repository activation must allowlist only
`java-sdk-evaluation.yml`; prerelease publication is not authorized.

Operational evaluation-use review is complete for explicit public downloads in
this bounded, attributed English ASR run, not production deployment, redistribution,
or legal signoff. The exact model LICENSE/NOTICES, NVIDIA Open Model License
use grant2.2 and accompanying trustworthy-AI terms, and OpenMDW1.1 were reviewed
by the coordinator. The catalog/card/packaged-notice discrepancy remains unresolved;
do not call all weights MIT. Retain all applicable notices; model/native
redistribution remains unauthorized. See `model.license_review` in `ci-lock.json`
for the precise restrictions and public sources.

The subsequent Linux x64 diagnostic
[run34398826339](https://github.com/jiec-msft/foundry-local/actions/runs/34398826339)
observed exactly the87-byte LF marker candidate; all15 other locked files matched.
It still failed before ASR. The complete observed manifest and a narrowly scoped
target-specific generated-marker lock proposal are recorded in
[the diagnostic evidence section](D094_EVALUATION.md#linux-x64-diagnostic-inventory).
The separately retrieved Linux ARM64 and macOS ARM64 diagnostics now confirm
the same marker-only difference and complete manifest on each target; see
[their individual evidence](D094_EVALUATION.md#arm64-diagnostic-inventories).
All three diagnostics still failed before transcription.

**Next dependency:** coordinator reviews the final22eb consumer source and owns
actual dispatch of the one remaining standard full matrix. One of the maximum
two full matrices and three diagnostic single-lane dispatches have occurred;
none should be duplicated. Linux x64/ARM64 and macOS ARM64 still require actual
native ASR. This evaluator has not dispatched, rerun, changed settings, normalized
model files, or accepted an unreviewed hash.

From the repository root, the offline readiness check exercises the actual
checked-in locks, immutable source/schema/selector and all five selections with
one previous full matrix. It makes no GitHub request and launches no native SDK:

```powershell
python -B -m unittest discover -s sdk_v2\java\evaluation -p test_preparation.py -k checked_in_readiness_lock_is_coherent -v
```

The coordinator-only dispatch inputs for the remaining matrix are:

```powershell
gh workflow run java-sdk-evaluation.yml --repo jiec-msft/foundry-local --ref mason/java-asr-evaluation -f sdk_sha=d0946a0764d9cfa4b3d684940d6d5c66165427b8 -f lane=full-matrix
```
