"""Run actual upstream model inference and write reproducible acoustic evidence.

This program does not fake model waveforms, and has no mock flag. If GPU,
weights or references are missing it writes a FAILED report, never a PASS.
Optional real Faster-Whisper re-transcription measures WER/CER via jiwer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.quality_report import analyze_wav
from studio import engines, qwen_runtime
from studio.verification import ENGINES, digest, report_root

QWEN_LANGUAGES = {
    "en": "English", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "de": "German", "fr": "French", "ru": "Russian", "pt": "Portuguese",
    "es": "Spanish", "it": "Italian",
}


def hardware() -> dict:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False)
        if result.returncode != 0 or not result.stdout.strip():
            return {"cuda_hardware_detected": False, "name": None,
                    "vram_total_mb": None, "vram_peak_mb": None}
        fields = [s.strip() for s in result.stdout.splitlines()[0].split(",")]
        return {"cuda_hardware_detected": True, "name": fields[0],
                "vram_total_mb": float(fields[1]) if len(fields) > 1 else None,
                "driver": fields[2] if len(fields) > 2 else None,
                "vram_peak_mb": None}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"cuda_hardware_detected": False, "name": None,
                "vram_total_mb": None, "vram_peak_mb": None}


def _asr(audio: Path, *, expected: str, language: str, model: str) -> dict:
    import jiwer
    python = os.getenv("WHISPER_PYTHON", "").strip()
    if not python:
        raise RuntimeError("Set WHISPER_PYTHON to an environment with faster-whisper.")
    result_path = audio.parent / "transcription.json"
    command = [python, str(Path(__file__).parent / "whisper_worker.py"),
               "--audio", str(audio), "--output", str(result_path),
               "--language", language, "--model", model]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900,
                               check=False)
    if completed.returncode:
        raise RuntimeError("Real Whisper ASR failed: " +
                           (completed.stderr or completed.stdout)[-400:])
    transcript = json.loads(result_path.read_text(encoding="utf-8"))["text"]
    def normalize(value: str) -> str:
        value = value.lower().replace("\u0640", "")
        value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
        return " ".join(value.split())
    source, recognized = normalize(expected), normalize(transcript)
    if not source:
        raise RuntimeError("No non-punctuation reference transcript for ASR.")
    return {"model": model, "language": language, "reference": expected,
            "transcript": transcript,
            "wer": round(float(jiwer.wer(source, recognized)), 4),
            "cer": round(float(jiwer.cer(source, recognized)), 4),
            "note": "ASR is an imperfect, model-dependent intelligibility proxy."}


def benchmark(*, engine: str, model: str, text: str, language: str,
              data: Path, reference: Path | None = None,
              reference_text: str = "", input_audio: Path | None = None,
              asr: bool = False, whisper_model: str = "small") -> dict:
    if engine not in ENGINES:
        raise ValueError("Unsupported benchmark engine")
    if asr and language not in {"ar", "en"}:
        raise ValueError("Independent ASR is configured for Arabic/English only")
    if not 1 <= len(text.strip()) <= 500:
        raise ValueError("Use a 1–500 character known transcript, not an empty recording.")
    destination = report_root(data) / engine
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "output.wav"
    report_file = destination / "report.json"
    text_file = destination / "input.txt"
    text_file.write_text(text, encoding="utf-8")
    # Invalidate any previous successful result before testing a new checkpoint.
    report_file.unlink(missing_ok=True)
    output.unlink(missing_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    report = {"schema_version": 1, "timestamp_utc": stamp,
              "engine": engine, "model": model, "result": "failed",
              "hardware": hardware(), "audio_sha256": None,
              "realtime_factor": None, "asr": None, "metrics": None,
              "note": "Actual upstream inference only; no mocked audio or subjective quality claims."}
    started = time.perf_counter()
    try:
        if engine == "chatterbox":
            if model not in {"multilingual-v3", "turbo", "nano"}:
                raise ValueError("Unknown Chatterbox checkpoint")
            engines.synthesize(
                text_file=text_file, reference=reference, language=language,
                output=output, model=model)
        elif engine == "qwen":
            if model not in {"design", "clone", "custom"}:
                raise ValueError("Qwen mode must be design, clone or custom")
            if language not in QWEN_LANGUAGES:
                raise ValueError("Qwen does not support this language")
            if model == "design" and not reference_text:
                raise ValueError("For Qwen design, --reference-text is the voice description")
            if model == "clone" and (reference is None or not reference_text):
                raise ValueError("Qwen clone requires reference WAV and exact transcript")
            qwen_runtime.synthesize(
                text_file=text_file, output=output, mode=model,
                language=QWEN_LANGUAGES[language],
                instruct=reference_text if model == "design" else (
                    "Speak with clear, natural diction." if model == "custom" else ""),
                ref_audio=reference if model == "clone" else None,
                ref_text=reference_text if model == "clone" else "",
                speaker="Ryan")
        elif engine == "applio":
            if input_audio is None or not input_audio.is_file():
                raise ValueError("Applio requires --input-audio with licensed speech")
            if not model:
                raise ValueError("Applio requires --model-id from an installed checkpoint")
            engines.convert(audio=input_audio, model_id=model, output=output)
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        from studio.app import _validate_output
        _validate_output(output)
        values = analyze_wav(output)
        report["metrics"] = values
        report["realtime_factor"] = round(
            report["elapsed_seconds"] / values["duration_seconds"], 3)
        if (values["duration_seconds"] < 0.3 or
            values["quiet_percent"] >= 98 or
            values["rms_dbfs"] is None or values["rms_dbfs"] < -55 or
            values["clipped_percent"] >= 1):
            raise RuntimeError("Acoustic smoke test rejected silent, clipped or too-short output.")
        if asr:
            report["asr"] = _asr(
                output, expected=text, language=language, model=whisper_model)
        report["audio_sha256"] = digest(output)
        report["result"] = "pass"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
    finally:
        temporary = report_file.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(report_file)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=ENGINES, required=True)
    parser.add_argument("--model", required=True, help="Chatterbox name, Qwen mode or Applio model ID")
    parser.add_argument("--text", required=True, help="Known intended spoken words")
    parser.add_argument("--language", default="en")
    parser.add_argument("--reference", type=Path, help="Consent-authorized WAV")
    parser.add_argument("--reference-text", default="", help="Qwen design description or clone seed transcript")
    parser.add_argument("--input-audio", type=Path, help="Applio source audio")
    parser.add_argument("--asr", action="store_true", help="Run real Faster-Whisper WER/CER test")
    parser.add_argument("--whisper-model", choices=["tiny", "base", "small", "medium", "large-v3"],
                        default="small")
    parser.add_argument("--data-dir", type=Path, default=Path(
        os.getenv("MINA_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data"))))
    args = parser.parse_args(argv)
    report = benchmark(engine=args.engine, model=args.model, text=args.text,
                       language=args.language, data=args.data_dir,
                       reference=args.reference, reference_text=args.reference_text,
                       input_audio=args.input_audio, asr=args.asr,
                       whisper_model=args.whisper_model)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
