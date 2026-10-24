"""Read local, reproducible acoustic-check evidence without inventing model success.

Evidence is a self-reported local benchmark (NOT cryptographically attested GPU
inference). Re-hash its actual generated audio and refuse stale/missing artifacts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ENGINES = ("qwen", "chatterbox", "applio")
MAX_REPORT_BYTES = 100 * 1024
MAX_AGE_DAYS = 30


def report_root(data: Path) -> Path:
    return data / "_verification"


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def read_report(data: Path, engine: str) -> dict:
    if engine not in ENGINES:
        raise ValueError("Unknown acoustic-check engine")
    folder = report_root(data) / engine
    report = folder / "report.json"
    answer = {"engine": engine, "state": "not_tested", "audio_verified": False,
              "evidence_type": "local_self_report", "note": "Run a real model smoke test first."}
    if not report.is_file() or report.stat().st_size > MAX_REPORT_BYTES:
        return answer
    try:
        document = json.loads(report.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(document["timestamp_utc"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if stamp.tzinfo is None or age < 0 or age > MAX_AGE_DAYS * 86400:
            return {**answer, "state": "stale"}
        if document["engine"] != engine or document["result"] != "pass":
            return {**answer, "state": "failed",
                    "error": str(document.get("error", "Verification did not pass."))[:200]}
        output = folder / "output.wav"
        # No external paths are accepted from JSON; only our own fixed folder.
        if not output.is_file() or digest(output) != document["audio_sha256"]:
            return {**answer, "state": "invalid_evidence"}
        if document["metrics"]["duration_seconds"] < 0.3:
            return {**answer, "state": "invalid_evidence"}
        return {**answer, "state": "locally_tested", "audio_verified": True,
                "reported_model": str(document["model"])[:100],
                "timestamp_utc": document["timestamp_utc"],
                "duration_seconds": document["metrics"]["duration_seconds"],
                "realtime_factor": document.get("realtime_factor"),
                "wer": document.get("asr", {}).get("wer") if document.get("asr") else None,
                "cer": document.get("asr", {}).get("cer") if document.get("asr") else None,
                "evidence_type": "local_self_report",
                "note": "Real WAV and local report exist; voice acting quality needs listening."}
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return {**answer, "state": "invalid_evidence"}


def status(data: Path) -> dict:
    return {"engines": [read_report(data, engine) for engine in ENGINES],
            "notes": "Local self-reported inference only; a green result is not independent identity, emotion or quality certification."}
