"""Verification evidence and installer contract; these tests do NOT use GPU inference."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import sys
import wave

import pytest
from fastapi.testclient import TestClient
from studio import app as server, verification, engines
from scripts import verify_real_audio, manage_engines


def pcm16(value: int = 1000, rate: int = 16000) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(value.to_bytes(2, "little", signed=True) * rate)
    return stream.getvalue()


@pytest.fixture
def root(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "DATA", tmp_path)
    return tmp_path


def write_pass(root, engine="chatterbox"):
    destination = verification.report_root(root) / engine
    destination.mkdir(parents=True, exist_ok=True)
    audio = destination / "output.wav"
    audio.write_bytes(pcm16())
    report = {
        "engine": engine, "model": "multilingual-v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "result": "pass", "audio_sha256": verification.digest(audio),
        "metrics": {"duration_seconds": 1.0},
        "realtime_factor": .9, "asr": {"wer": .2, "cer": .12},
    }
    (destination / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return audio, report


def test_no_report_no_claim_of_model_success(root):
    data = verification.status(root)
    assert len(data["engines"]) == 3
    assert all(e["state"] == "not_tested" and e["audio_verified"] is False
               for e in data["engines"])
    with TestClient(server.app) as client:
        response = client.get("/api/verification/status")
        assert response.status_code == 200
        assert not any(x["audio_verified"] for x in response.json()["engines"])


def test_valid_report_is_self_reported_and_rehashed(root):
    audio, doc = write_pass(root)
    item = verification.read_report(root, "chatterbox")
    assert item["state"] == "locally_tested"
    assert item["audio_verified"] is True
    assert item["evidence_type"] == "local_self_report"
    assert item["wer"] == .2
    with TestClient(server.app) as client:
        assert client.get("/api/verification/status").json()["engines"][1]["state"] == "locally_tested"
    audio.write_bytes(audio.read_bytes() + b"TAMPER")
    assert verification.read_report(root, "chatterbox")["state"] == "invalid_evidence"


def test_stale_bad_and_failed_reports_never_pass(root):
    audio, report = write_pass(root, "qwen")
    file = verification.report_root(root) / "qwen" / "report.json"
    report["timestamp_utc"] = (datetime.now(timezone.utc) -
                                timedelta(days=32)).isoformat()
    file.write_text(json.dumps(report))
    assert verification.read_report(root, "qwen")["state"] == "stale"
    report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    report["result"] = "failed"
    report["error"] = "No GPU configured"
    file.write_text(json.dumps(report))
    assert verification.read_report(root, "qwen")["state"] == "failed"
    report["result"] = "pass"
    report["audio_sha256"] = "0"*64
    file.write_text(json.dumps(report))
    assert verification.read_report(root, "qwen")["state"] == "invalid_evidence"
    with pytest.raises(ValueError):
        verification.read_report(root, "../../etc")


def test_failed_real_engine_stays_failed_and_invalidates_previous_output(root, monkeypatch):
    write_pass(root, "chatterbox")
    def fail(**kwargs):
        raise RuntimeError("Weights unavailable: real engine not installed")
    monkeypatch.setattr(engines, "synthesize", fail)
    result = verify_real_audio.benchmark(
        engine="chatterbox", model="multilingual-v3",
        language="ar", text="هذه جملة اختبار", data=root)
    assert result["result"] == "failed"
    assert result["audio_sha256"] is None
    assert "Weights unavailable" in result["error"]
    assert not (verification.report_root(root)/"chatterbox"/"output.wav").exists()
    assert verification.read_report(root, "chatterbox")["audio_verified"] is False


def test_real_wav_processing_but_model_is_mocked_in_unit_test(root, monkeypatch):
    called = []
    def fake_model(**kwargs):
        called.append(kwargs)
        kwargs["output"].write_bytes(pcm16())
    monkeypatch.setattr(engines, "synthesize", fake_model)
    # This exercises reporting logic with a synthetic fixture, not an acoustic model.
    result = verify_real_audio.benchmark(
        engine="chatterbox", model="multilingual-v3",
        language="ar", text="مرحبا بالعالم", data=root)
    assert result["result"] == "pass"
    assert result["metrics"]["duration_seconds"] == 1.0
    assert result["audio_sha256"]
    assert result["asr"] is None
    assert len(called) == 1
    assert verification.read_report(root, "chatterbox")["evidence_type"] == "local_self_report"


def test_silent_output_rejected_despite_valid_wav(root, monkeypatch):
    monkeypatch.setattr(engines,"synthesize",
                        lambda **kw: kw["output"].write_bytes(pcm16(0)))
    item = verify_real_audio.benchmark(engine="chatterbox", model="multilingual-v3",
                                      language="en", text="Hello", data=root)
    assert item["result"] == "failed"
    assert verification.read_report(root,"chatterbox")["audio_verified"] is False


def test_model_manager_isolated_python_metadata_and_version_preflight(monkeypatch):
    assert manage_engines.SPECS["qwen"]["env_var"] == "QWEN_PYTHON"
    assert manage_engines.SPECS["chatterbox"]["env_var"] == "CHATTERBOX_PYTHON"
    assert manage_engines.probe(sys.executable,"json")["module_available"] is True
    assert "applio" not in manage_engines.SPECS
    class InvalidVersion:
        stdout="3.10\n"
    monkeypatch.setattr(manage_engines.subprocess, "run",
                        lambda *args, **kwargs: InvalidVersion())
    with pytest.raises(RuntimeError, match="requires Python 3.12"):
        manage_engines.install("qwen")
    with pytest.raises(ValueError):
        manage_engines.install("not-approved")
