"""Audit a consented local WAV training manifest. No model training occurs.

Expected JSONL records:
{"audio":"clips/001.wav","text":"مرحباً","speaker_id":"s1","language":"ar","consent":true,"split":"train"}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import wave


def audit_dataset(root: Path, manifest: Path) -> dict:
    root = root.resolve()
    manifest = manifest.resolve()
    if not root.is_dir():
        raise ValueError("Dataset root not found.")
    records = []
    issues = []
    seen = set()
    counts = {}
    minutes = 0.0
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            rel = item["audio"]
            if not isinstance(rel, str) or not rel:
                raise ValueError("Invalid audio path")
            audio = (root / rel).resolve()
            if not audio.is_relative_to(root) or audio.suffix.lower() != ".wav":
                raise ValueError("Audio path must be an in-dataset WAV")
            if audio in seen:
                raise ValueError("Duplicate recording")
            seen.add(audio)
            if item.get("consent") is not True:
                raise ValueError("Explicit voice-use consent is required")
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                raise ValueError("Missing transcript")
            if item.get("language") not in {"ar", "en"}:
                raise ValueError("Only Arabic/English datasets validated in this pilot")
            if not item.get("speaker_id"):
                raise ValueError("Missing speaker ID")
            if item.get("split") not in {"train", "validation", "test"}:
                raise ValueError("Missing/invalid dataset split")
            if not audio.exists():
                raise ValueError("Audio file missing")
            with wave.open(str(audio), "rb") as wav:
                if wav.getcomptype() != "NONE" or wav.getsampwidth() != 2:
                    raise ValueError("Expected 16-bit PCM WAV")
                if wav.getnchannels() not in (1, 2) or wav.getframerate() < 16000:
                    raise ValueError("Invalid channels or sample rate")
                duration = wav.getnframes() / wav.getframerate()
                if not 1.0 <= duration <= 30.0:
                    raise ValueError("Voice clip outside 1–30 seconds")
            key = item["split"]
            counts[key] = counts.get(key, 0) + 1
            minutes += duration / 60.0
            records.append({"audio": rel, "seconds": round(duration, 2), "split": key})
        except (KeyError, ValueError, TypeError, OSError, wave.Error, json.JSONDecodeError) as exc:
            issues.append({"line": number, "reason": str(exc)})
    return {
        "accepted": len(records),
        "minutes": round(minutes, 2),
        "splits": counts,
        "issues": issues,
        "ready_for_training": len(records) >= 10 and not issues and all(counts.get(x, 0) > 0 for x in ("train", "validation", "test")),
        "notice": "Manifest checks do not verify speaker consent, rights or acoustic quality independently.",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, required=True)
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--report", type=Path)
    args = cli.parse_args()
    result = audit_dataset(args.root, args.manifest)
    document = json.dumps(result, indent=2, ensure_ascii=False)
    print(document)
    if args.report:
        args.report.write_text(document + "\n", encoding="utf-8")
    if result["issues"] or not result["ready_for_training"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
