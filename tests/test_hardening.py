"""Security and failure-path tests: real HTTP + mocked model work."""
import io
from pathlib import Path
import time
import wave

import pytest
from fastapi.testclient import TestClient

from studio import app as server
from studio import engines


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with server.job_lock:
        server.jobs.clear()
    with TestClient(server.app) as test_client:
        yield test_client


def _wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(b"\0\0" * 100)
    return buf.getvalue()


def test_cross_site_form_request_rejected(client):
    response = client.post(
        "/api/speech", data={"text": "hello", "consent": "true"},
        headers={"Origin": "https://untrusted.example"}
    )
    assert response.status_code == 403


def test_host_header_dns_rebinding_rejected(client):
    response = client.get("/api/health", headers={"Host": "evil.invalid:1234"})
    assert response.status_code == 400


def test_invalid_audio_header_rejected_and_directory_cleaned(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id":"chatterbox","configured":True}])
    response = client.post(
        "/api/speech", data={"text":"hello","consent":"true"},
        files={"reference":("hello.wav",b"Z"*128,"audio/wav")}
    )
    assert response.status_code == 422
    assert not list(server.DATA.iterdir())


def test_queue_saturation_returns_429(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id":"chatterbox","configured":True}])
    monkeypatch.setattr(server, "MAX_ACTIVE_JOBS", 0)
    response = client.post("/api/speech", data={"text":"hello","consent":"true"})
    assert response.status_code == 429


def test_accepts_valid_voice_reference(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id":"chatterbox","configured":True}])
    def fake_generation(**kwargs):
        assert Path(kwargs["reference"]).read_bytes() == _wav_bytes()
        Path(kwargs["output"]).write_bytes(_wav_bytes())
    monkeypatch.setattr(engines, "synthesize", fake_generation)
    response = client.post(
        "/api/speech",
        data={"text":"مرحبا"*90, "language":"ar","consent":"true"},
        files={"reference":("myvoice.wav",_wav_bytes(),"audio/wav")}
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(100):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in ("completed","failed"):
            break
        time.sleep(0.01)
    assert status["status"] == "completed", status


def test_rejects_fake_output_even_if_worker_returns_success(client, monkeypatch):
    monkeypatch.setattr(engines, "status", lambda: [{"id":"chatterbox","configured":True}])
    def fake_generation(**kwargs):
        Path(kwargs["output"]).write_bytes(b"not audio")
    monkeypatch.setattr(engines, "synthesize", fake_generation)
    response = client.post("/api/speech", data={"text":"test","consent":"true"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    for _ in range(100):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] in ("completed","failed"):
            break
        time.sleep(0.01)
    assert status["status"] == "failed"
    assert client.get(f"/api/jobs/{job_id}/audio").status_code == 404


def test_old_jobs_are_removed_with_audio_on_new_request(client, monkeypatch):
    monkeypatch.setattr(server, "JOB_TTL_SECONDS", 100)
    job_id = "abc123"
    folder = server.DATA / job_id
    folder.mkdir()
    (folder / "voice.wav").write_bytes(_wav_bytes())
    with server.job_lock:
        server.jobs[job_id] = {
            "status":"completed","updated":time.time()-1000,
            "id":job_id,"engine":"test","created":1,"download":None,"error":None
        }
    server._new_job("test")
    assert not folder.exists()
    assert job_id not in server.jobs
