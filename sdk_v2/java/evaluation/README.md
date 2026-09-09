# Public Java ASR smoke evaluation

**Preparation only: READY_FOR_SDK. No Java model run or hosted ASR result is claimed.**
This directory is independently authored evaluation code, not an SDK implementation.
The ten fixed English utterances are a smoke set, **never a product quality claim**.
They are not representative of languages, accents, microphones, conversational speech,
long recordings, accessibility needs, or the population of users.

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

Normal consumption and unit tests need only Python 3.11+ stdlib and the committed
WAVs. No model, runtime, native build, corpus download, decoder, or account is needed:

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

The input contract is `measurement.schema.json`. After authorized actual SDK execution:

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

Measurement semantics for the future fixed-SDK adapter:

- Record SDK commit, runtime version and package SHA256, exact model ID/version/hash,
  JDK version/vendor, OS, and actual host/JVM/native architecture, not just runner labels.
- Readiness is the elapsed monotonic duration of explicit runtime/model preparation
  until inference-ready, with cold/warm state explicit. It is not first-token latency.
- Feed 20 ms PCM chunks against monotonic deadlines at the original 16000 Hz rate;
  record the actual chunk duration (up to 100 ms is accepted, never a whole-file
  burst disguised as streaming). Timing timestamps are milliseconds from one
  process-local monotonic origin. `feed_started_ms` is first submitted audio;
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

The fixed-SDK adapter must execute `transcribe --wav` for all ten committed WAVs,
then paced streaming of the same ten, plus a cancellation/cleanup probe. Preserve
batch hypotheses in raw JSONL and score the final paced hypotheses in the primary
measurement. The adapter/event mapping is deliberately not guessed in this revision.

## Fixed SDK dependency and ABI

`sdk-contract.json` records the public runtime tuple supplied by the coordinator:
`Microsoft.AI.Foundry.Local.Runtime 2.0.1`, ORT `1.28.0`, and
`Microsoft.ML.OnnxRuntimeGenAI.Foundry 0.15.2`; Java 17 with JNA.
The runtime package and its own C header are SHA256-pinned in that file.
**Use the package's own API_VERSION=1 header.** Public main and the `v2.0.1`
tag header have API_VERSION=2 and must not be used with that packaged binary.
This preparation has not downloaded or executed the runtime.

Expected CLI: `identify`, `prepare --explicit-download`, `transcribe --wav`,
`stream --wav` (paced PCM) or `--pcm`, optional `--cancel-after-ms`, with
explicit `--runtime-dir`/`--cache-dir` and JSON-lines stdout. An immutable SDK
commit or artifact, launcher, JSONL event schema, dependency/model/JDK download
pins and license review are still required. SDK API/build changes belong to the
coordinator/SDK worker, not this directory.

## Hosted CI is staged, not enabled

The two `java-sdk*.yml` workflows are scoped to evaluation paths. The small
unit workflow is offline on a standard `ubuntu-24.04` host; model evaluation is
**workflow_dispatch only**, owner/repository/ref guarded, and fails closed against
`ci-lock.json`. Its integration entry point intentionally exits nonzero until the
immutable SDK has been bound. Neither that gate nor parsing native headers is
evidence that an ASR model ran. The fork Actions setting remains disabled.

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
Do not enable inherited workflows. Later enablement must allowlist only the approved
Java workflow(s); prerelease publication and actual CI require separate permission.

**Next dependency:** coordinator supplies the immutable SDK SHA/artifact and JSONL
contract; integrate only in owned evaluation/workflow paths, then obtain the local
compute slot. Only after real local Windows success, complete public download hashes,
and dispatch permission may the coordinator authorize Actions enablement and a bounded
matrix. No runtime, model, CI, prerelease, issue, or PR action is implied by this preparation.
