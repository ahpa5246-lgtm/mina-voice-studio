"""Run a REAL end-to-end local synthesis or voice-conversion smoke test.

This script makes no fake recordings and does not require the website to run.
Requires the relevant model environment, downloaded weights and consented audio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from studio import engines
from scripts.quality_report import analyze_wav


def benchmark(operation: str, *, output: Path, text: str | None = None,
              reference: Path | None = None, language: str = "ar",
              audio: Path | None = None, model_id: str | None = None) -> dict:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if operation == "speech":
        if not text or not text.strip():
            raise ValueError("Speech smoke test requires --text.")
        text_path = output.with_name(output.stem + ".text.txt")
        text_path.write_text(text, encoding="utf-8")
        engines.synthesize(text_file=text_path, reference=reference, language=language, output=output)
    elif operation == "conversion":
        if audio is None or model_id is None:
            raise ValueError("Conversion smoke test needs --audio and --model-id.")
        engines.convert(audio=audio, model_id=model_id, output=output)
    else:
        raise ValueError("Unknown operation.")
    elapsed = time.perf_counter() - started
    report = analyze_wav(output)
    report.update({
        "operation": operation,
        "elapsed_seconds": round(elapsed, 3),
        "realtime_factor": round(elapsed / report["duration_seconds"], 3),
        "notes": "Technical signal diagnostics only; no naturalness, accent or voice-identity score.",
    })
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=["speech", "conversion"], default="speech")
    parser.add_argument("--text", help="Text to synthesize (requires Chatterbox configured)")
    parser.add_argument("--reference", type=Path, help="Authorized reference voice")
    parser.add_argument("--language", default="ar")
    parser.add_argument("--audio", type=Path, help="Input recording for Applio conversion")
    parser.add_argument("--model-id", help="An ID returned from /api/models")
    parser.add_argument("--output", type=Path, default=Path("data/manual-benchmark.wav"))
    parser.add_argument("--report", type=Path, help="Write the same JSON report to disk")
    args = parser.parse_args()
    report = benchmark(
        args.operation, output=args.output, text=args.text,
        reference=args.reference, language=args.language,
        audio=args.audio, model_id=args.model_id,
    )
    body = json.dumps(report, indent=2, ensure_ascii=False)
    print(body)
    if args.report:
        args.report.write_text(body + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
