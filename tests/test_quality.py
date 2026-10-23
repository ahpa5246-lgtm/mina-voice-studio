import struct
from pathlib import Path
import wave

import pytest
from scripts.quality_report import analyze_wav


def _write(path: Path, frames: list[int]):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(struct.pack("<" + "h" * len(frames), *frames))


def test_quality_detects_clipping(tmp_path):
    target = tmp_path / "test.wav"
    _write(target, [32767, -32768, 0, 20000] * 4000)
    r = analyze_wav(target)
    assert r["duration_seconds"] == 1.0
    assert r["clipped_percent"] == 50.0
    assert "Possible waveform clipping" in r["warnings"]


def test_quality_detects_silence(tmp_path):
    target = tmp_path / "test.wav"
    _write(target, [0] * 16000)
    r = analyze_wav(target)
    assert r["rms_dbfs"] is None
    assert r["quiet_percent"] == 100.0
    assert "Mostly quiet waveform" in r["warnings"]


def test_quality_invalid_file_is_not_passed(tmp_path):
    target = tmp_path / "broken.wav"
    target.write_bytes(b"not wave")
    with pytest.raises((ValueError, wave.Error, EOFError)):
        analyze_wav(target)
