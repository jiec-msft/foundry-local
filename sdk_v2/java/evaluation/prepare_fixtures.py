# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Reproduce the fixed public LibriSpeech smoke set; never invokes recognition."""

import argparse
import hashlib
import io
import json
import platform
import shutil
import tarfile
import urllib.request
import wave
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
SOURCES = {
    "dev-clean": {
        "url": "https://www.openslr.org/resources/12/dev-clean.tar.gz",
        "published_md5": "42e2234ba48799c1f50f24a7926300a1",
    },
    "dev-other": {
        "url": "https://www.openslr.org/resources/12/dev-other.tar.gz",
        "published_md5": "c8d0bcc9cca99d4f8b62fcc847357931",
    },
}
SELECTION = (
    "For each subset, sort (speaker, chapter, utterance) numerically; select the first "
    "complete 4.000-10.000 second utterance from each of the first five eligible "
    "distinct speakers. Require source mono/16000Hz/16-bit FLAC. No trimming, "
    "resampling, silence removal, transcription filtering, or recognition."
)


def digest(path, algorithm="sha256"):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, algorithm).hexdigest()


def source_archive(cache, subset, expected_sha256=None):
    """Cache one archive per subset; never overwrite an invalid existing cache."""
    spec = SOURCES[subset]
    destination = cache / f"{subset}.tar.gz"
    cache.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        partial = destination.with_suffix(".gz.partial")
        if partial.exists():
            raise ValueError(f"Partial download exists; inspect/remove explicitly: {partial}")
        with urllib.request.urlopen(spec["url"], timeout=120) as response, partial.open("xb") as output:
            shutil.copyfileobj(response, output)
        if digest(partial, "md5") != spec["published_md5"]:
            raise ValueError(f"OpenSLR published MD5 mismatch: {partial}")
        if expected_sha256 and digest(partial) != expected_sha256:
            raise ValueError(f"Pinned SHA256 mismatch: {partial}")
        partial.rename(destination)
    if digest(destination, "md5") != spec["published_md5"]:
        raise ValueError(f"OpenSLR published MD5 mismatch: {destination}")
    sha256 = digest(destination)
    if expected_sha256 and sha256 != expected_sha256:
        raise ValueError(f"Pinned SHA256 mismatch: {destination}")
    return destination, sha256


def flac_streaminfo(data):
    if len(data) < 42 or data[:4] != b"fLaC" or data[4] & 0x7F != 0 or int.from_bytes(data[5:8], "big") != 34:
        raise ValueError("Expected FLAC STREAMINFO as first metadata block")
    packed = int.from_bytes(data[18:26], "big")
    return {
        "sample_rate": packed >> 44,
        "channels": ((packed >> 41) & 7) + 1,
        "bits_per_sample": ((packed >> 36) & 31) + 1,
        "frames": packed & ((1 << 36) - 1),
    }


def read_member(archive, name):
    member = archive.getmember(name)
    if not member.isfile():
        raise ValueError(f"Expected regular archive member: {name}")
    with archive.extractfile(member) as source:
        return source.read()


def curate(archive_path, subset, output, soundfile):
    samples = []
    with tarfile.open(archive_path, "r:gz") as archive:
        members = [m for m in archive.getmembers() if m.isfile() and m.name.endswith(".flac")]
        members.sort(key=lambda m: tuple(int(n) for n in PurePosixPath(m.name).stem.split("-")))
        seen = set()
        for member in members:
            utterance = PurePosixPath(member.name).stem
            speaker, chapter, _ = utterance.split("-")
            if speaker in seen:
                continue
            flac = read_member(archive, member.name)
            info = flac_streaminfo(flac)
            if (info["sample_rate"], info["channels"], info["bits_per_sample"]) != (16000, 1, 16):
                raise ValueError(f"Unexpected source format: {member.name}: {info}")
            if not 64000 <= info["frames"] <= 160000:
                continue
            transcript_path = str(PurePosixPath(member.name).parent / f"{speaker}-{chapter}.trans.txt")
            transcript_bytes = read_member(archive, transcript_path)
            references = dict(line.split(" ", 1) for line in transcript_bytes.decode("utf-8").splitlines())
            reference = references[utterance]
            pcm, sample_rate = soundfile.read(io.BytesIO(flac), dtype="int16", always_2d=True)
            if sample_rate != 16000 or pcm.shape != (info["frames"], 1):
                raise ValueError(f"Decoded frames differ from STREAMINFO: {utterance}")
            wav_path = output / "fixtures" / f"{utterance}.wav"
            wav_path.parent.mkdir(parents=True, exist_ok=True)
            pcm_bytes = pcm.astype("<i2", copy=False).tobytes()
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(pcm_bytes)
            samples.append({
                "id": utterance,
                "subset": subset,
                "speaker_id": speaker,
                "chapter_id": chapter,
                "source_archive": archive_path.name,
                "source_member": member.name,
                "source_flac_sha256": hashlib.sha256(flac).hexdigest(),
                "source_transcript_member": transcript_path,
                "source_transcript_sha256": hashlib.sha256(transcript_bytes).hexdigest(),
                "reference_raw": reference,
                "wav_path": f"fixtures/{utterance}.wav",
                "wav_sha256": digest(wav_path),
                "pcm_sha256": hashlib.sha256(pcm_bytes).hexdigest(),
                "wav_bytes": wav_path.stat().st_size,
                "frames": info["frames"],
                "duration_seconds": info["frames"] / 16000,
            })
            seen.add(speaker)
            if len(samples) == 5:
                break
        if len(samples) != 5:
            raise ValueError(f"Not enough eligible distinct speakers in {subset}")
        license_bytes = read_member(archive, "LibriSpeech/LICENSE.TXT")
        (output / "fixtures" / "LICENSE.TXT").write_bytes(license_bytes)
    return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True, help="Explicit reusable development-archive cache")
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "reproduced")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.json", help="Pinned source manifest")
    parser.add_argument("--initial-curation", action="store_true", help="Only for first pre-recognition freeze")
    parser.add_argument("--decoder-report", type=Path, help="pip --report JSON with public wheel hashes")
    args = parser.parse_args()
    import cffi
    import numpy
    import pycparser
    import soundfile

    pinned = None if args.initial_curation else json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.output.resolve() == ROOT and not args.initial_curation:
        raise ValueError("Reproduce into build output; do not overwrite committed fixtures")
    args.output.mkdir(parents=True, exist_ok=True)
    archives, samples = {}, []
    for subset in SOURCES:
        expected = None if pinned is None else pinned["archives"][subset]["sha256"]
        archive, sha256 = source_archive(args.cache.resolve(), subset, expected)
        archives[subset] = {**SOURCES[subset], "sha256": sha256, "bytes": archive.stat().st_size}
        samples.extend(curate(archive, subset, args.output, soundfile))
    decoder = {
        "python": platform.python_version(),
        "soundfile": soundfile.__version__,
        "libsndfile": soundfile.__libsndfile_version__,
        "numpy": numpy.__version__,
        "cffi": cffi.__version__,
        "pycparser": pycparser.__version__,
        "operation": "libsoundfile FLAC decode to int16; little-endian bytes; Python wave canonical 44-byte PCM header",
    }
    if args.decoder_report:
        report = json.loads(args.decoder_report.read_text(encoding="utf-8"))
        decoder["packages"] = [{
            "name": item["metadata"]["name"],
            "version": item["metadata"]["version"],
            "url": item["download_info"]["url"],
            "sha256": item["download_info"]["archive_info"]["hashes"]["sha256"],
        } for item in report["install"]]
    result = {
        "schema_version": 1,
        "fixture_set_id": "librispeech-dev-smoke-10-v1",
        "source": "https://www.openslr.org/12",
        "published_checksums": "https://www.openslr.org/resources/12/md5sum.txt",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "LibriSpeech: Vassil Panayotov, Guoguo Chen, Daniel Povey, Sanjeev Khudanpur; LibriVox readers",
        "selection_policy": SELECTION,
        "format": {"container": "WAV", "encoding": "PCM_S16LE", "sample_rate": 16000, "channels": 1},
        "archives": archives,
        "decoder": decoder,
        "samples": samples,
    }
    if pinned is not None and samples != pinned["samples"]:
        raise ValueError("Reproduced selection/audio/transcripts differ from frozen manifest")
    (args.output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(samples)} fixed fixtures in {args.output}")


if __name__ == "__main__":
    main()
