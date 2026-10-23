"""Technical WAV diagnostics; NOT a listener/MOS or speaker-similarity score.

Example: python scripts/quality_report.py data/<job-id>/output.wav
Only uncompressed 16-bit PCM WAV is supported by this small dependency-free
diagnostic. Chatterbox output normally uses this format.
"""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import sys
import wave

MAX_ANALYSIS_SECONDS = 3600


def _dbfs(value: float) -> float | None:
    return round(20 * math.log10(value / 32768.0), 2) if value > 0 else None


def analyze_wav(path: Path) -> dict:
    path = Path(path)
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        nframes = source.getnframes()
        if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
            raise ValueError("Expected uncompressed 16-bit PCM WAV.")
        if channels not in (1, 2) or not 8000 <= rate <= 192000:
            raise ValueError("Unsupported channel count or sampling frequency.")
        if nframes == 0 or nframes > MAX_ANALYSIS_SECONDS * rate:
            raise ValueError("Missing samples or audio longer than one hour.")
        total = 0
        square_sum = 0
        peak = 0
        silent = 0
        clipped = 0
        first_loud = None
        last_loud = None
        while True:
            chunk = source.readframes(16384)
            if not chunk:
                break
            samples = array("h")
            samples.frombytes(chunk)
            if sys.byteorder != "little":
                samples.byteswap()
            for value in samples:
                amplitude = abs(value)
                total += 1
                square_sum += value * value
                if amplitude > peak:
                    peak = amplitude
                if amplitude <= 104:  # About -50dBFS
                    silent += 1
                else:
                    position = (total - 1) // channels
                    if first_loud is None:
                        first_loud = position
                    last_loud = position
                if amplitude >= 32760:
                    clipped += 1
        if total != nframes * channels:
            raise ValueError("WAV header and payload disagree.")
    duration = nframes / rate
    clipped_pct = (clipped / total) * 100
    quiet_pct = (silent / total) * 100
    result = {
        "file": path.name,
        "duration_seconds": round(duration, 3),
        "sample_rate": rate,
        "channels": channels,
        "rms_dbfs": _dbfs(math.sqrt(square_sum / total)),
        "peak_dbfs": _dbfs(peak),
        "clipped_percent": round(clipped_pct, 3),
        "quiet_percent": round(quiet_pct, 3),
        "leading_quiet_seconds": round((first_loud if first_loud is not None else nframes) / rate, 3),
        "trailing_quiet_seconds": round((nframes - last_loud - 1 if last_loud is not None else nframes) / rate, 3),
        "warnings": [],
    }
    if clipped_pct >= 0.1:
        result["warnings"].append("Possible waveform clipping")
    if quiet_pct > 95:
        result["warnings"].append("Mostly quiet waveform")
    if duration < 0.3:
        result["warnings"].append("Very short output")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("--out", type=Path, help="Optional machine-readable JSON report path")
    args = parser.parse_args()
    report = analyze_wav(args.wav)
    result = json.dumps(report, ensure_ascii=False, indent=2)
    print(result)
    if args.out:
        args.out.write_text(result + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
