"""Unit tests validate API workflow; no audio-quality claims."""
import time
from pathlib import Path
import wave

from fastapi.testclient import TestClient
import pytest
from studio import app as server
from studio import engines


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    return TestClient(server.app)


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "MINA" in response.text


def test_health_contract(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert len(response.json()["engines"]) == 4


def test_consent_required(client):
    assert client.post("/api/speech", data={"text": "hello", "language": "en"}).status_code == 422


def test_requires_engine(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id": "chatterbox", "configured": False}])
    assert client.post("/api/speech", data={"text": "hello", "language": "en", "consent": "true"}).status_code == 503


def test_invalid_language(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id": "chatterbox", "configured": True}])
    assert client.post("/api/speech", data={"text": "hello", "language": "xx", "consent": "true"}).status_code == 422


def test_file_size_limit(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id": "chatterbox", "configured": True}])
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 3)
    response = client.post("/api/speech", data={"text": "hello", "consent": "true"}, files={"reference": ("a.wav", b"12345", "audio/wav")})
    assert response.status_code == 413


def test_job_workflow_stub_only(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id": "chatterbox", "configured": True}])
    def stub(**kwargs):
        assert Path(kwargs["text_file"]).read_text() == "Hello test"
        with wave.open(str(kwargs["output"]), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(b"\x00\x00" * 200)
    monkeypatch.setattr(engines, "synthesize", stub)
    response = client.post("/api/speech", data={"text": "Hello test", "language": "en", "consent": "true"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(100):
        job = client.get("/api/jobs/" + job_id).json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.01)
    assert job["status"] == "completed", job
    assert client.get(job["download"]).status_code == 200


def test_applio_model_allowlist(tmp_path, monkeypatch):
    root = tmp_path / "applio"
    (root / "logs" / "voice").mkdir(parents=True)
    (root / "core.py").write_text("# test")
    (root / "logs" / "voice" / "myvoice.pth").write_bytes(b"test")
    monkeypatch.setenv("APPLIO_ROOT", str(root))
    assert engines.model_catalog()[0]["id"] == "voice/myvoice.pth"
    model, index = engines.resolve_model("voice/myvoice.pth")
    assert model.is_file() and index is None
    with pytest.raises(engines.EngineError):
        engines.resolve_model("../../arbitrary.pth")


def test_planned_engines_not_falsely_marked_ready(client):
    statuses = {engine["id"]: engine for engine in client.get("/api/health").json()["engines"]}
    assert statuses["gpt-sovits"]["configured"] is False
    assert statuses["tts-webui"]["configured"] is False
