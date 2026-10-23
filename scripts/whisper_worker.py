"""Transcribe with an installed faster-whisper model in a separate Python venv."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default="auto")
    parser.add_argument("--model", default="small")
    args = parser.parse_args()
    if args.model not in {"tiny", "base", "small", "medium", "large-v3"}:
        raise ValueError("Unsupported Whisper model selection")
    if args.language not in {"auto", "ar", "en"}:
        raise ValueError("Language must be auto, ar or en")
    from faster_whisper import WhisperModel
    import os
    device = os.getenv("WHISPER_DEVICE", "auto")
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Unsupported Whisper device")
    model = WhisperModel(args.model, device=device, compute_type="auto")
    segments, info = model.transcribe(
        args.audio,
        beam_size=5,
        language=None if args.language == "auto" else args.language,
        vad_filter=True,
    )
    results = [
        {"start": round(segment.start, 3), "end": round(segment.end, 3),
         "text": segment.text.strip()}
        for segment in segments
    ]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"language": info.language, "segments": results,
         "text": " ".join(item["text"] for item in results)},
        ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
