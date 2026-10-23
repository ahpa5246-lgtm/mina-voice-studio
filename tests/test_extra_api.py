"""HTTP integration of genuine local processing and honest optional-engine gating."""
from array import array
import io
import json
from pathlib import Path
import time
import wave

import pytest
from fastapi.testclient import TestClient

from studio import app as server, extras, engines, providers


def voice_sample():
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((b"\x00\x14\x00\xed") * 800)
    return out.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    with server.job_lock:
        server.jobs.clear()
    with TestClient(server.app) as c:
        yield c
    with server.job_lock:
        server.jobs.clear()


def wait(c, job_id):
    for i in range(1000):
        result = c.get("/api/jobs/" + job_id).json()
        if result["status"] in ("completed", "failed"):
            return result
        time.sleep(.005)
    raise AssertionError("No job result")


def test_tools_endpoint_exposes_real_state(client, monkeypatch):
    monkeypatch.delenv("WHISPER_PYTHON", raising=False)
    status = client.get("/api/tools")
    assert status.status_code == 200
    features = {v["id"]:v for v in status.json()["tools"]}
    assert features["enhance"]["ready"] is True
    assert features["realtime"]["ready"] is False
    assert features["training"]["ready"] is False
    assert features["transcribe"]["ready"] is False


def test_voice_library_round_trip(client):
    assert client.get("/api/voices").json()["voices"] == []
    created = client.post("/api/voices",data={"name":"My voice","consent":"true"},
            files={"audio":("sample.wav",voice_sample(),"audio/wav")})
    assert created.status_code == 201, created.text
    voice_id = created.json()["voice"]["id"]
    assert client.get("/api/voices").json()["voices"][0]["name"] == "My voice"
    response = client.get("/api/voices/" + voice_id + "/audio")
    assert response.status_code == 200
    assert response.content == voice_sample()
    assert client.delete("/api/voices/" + voice_id).status_code == 200
    assert client.get("/api/voices/" + voice_id + "/audio").status_code == 404


def test_voice_cannot_be_saved_without_consent(client):
    response = client.post("/api/voices",data={"name":"Not authorized"},
            files={"audio":("voice.wav",voice_sample(),"audio/wav")})
    assert response.status_code == 422
    assert client.get("/api/voices").json()["voices"] == []


def test_voice_rejects_malicious_id(client):
    assert client.delete("/api/voices/..%2F..%2Fsecrets").status_code in (404, 422)
    assert client.get("/api/voices/this-is-not-hex/audio").status_code == 404


def test_real_wav_cleanup_pipeline(client):
    response = client.post("/api/enhance", files={"audio":("audio.wav",voice_sample(),"audio/wav")},
                           data={"highpass_hz":"65","peak_dbfs":"-1","noise_gate":"true"})
    assert response.status_code == 202, response.text
    result = wait(client,response.json()["id"])
    assert result["status"] == "completed", result
    output = client.get(result["download"])
    assert output.status_code == 200
    assert output.content.startswith(b"RIFF")
    assert output.content != voice_sample()


def test_real_wav_quality_analyzer(client):
    response = client.post("/api/analyze",files={"audio":("audio.wav",voice_sample(),"audio/wav")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["sample_rate"] == 16000
    assert result["duration_seconds"] == 0.1
    assert "clipped_percent" in result


def test_audio_tools_reject_other_formats(client):
    sample = voice_sample()
    assert client.post("/api/enhance",files={"audio":("audio.mp3",sample,"audio/mpeg")}).status_code == 422
    assert client.post("/api/analyze",files={"audio":("audio.mp3",sample,"audio/mpeg")}).status_code == 422


def test_unauthorized_cross_origin_is_rejected(client):
    response=client.post("/api/voices",data={"name":"Cross origin","consent":"true"},
                         files={"audio":("voice.wav",voice_sample(),"audio/wav")},
                         headers={"Origin":"https://evil.example"})
    assert response.status_code == 403


def test_library_not_purged_by_stale_job_cleanup(client,monkeypatch):
    created=client.post("/api/voices",data={"name":"Permanent","consent":"true"},
                        files={"audio":("voice.wav",voice_sample(),"audio/wav")})
    voice_id=created.json()["voice"]["id"]
    monkeypatch.setattr(server,"JOB_TTL_SECONDS",-1)
    server._new_job("cleanup-test")
    assert client.get(f"/api/voices/{voice_id}/audio").status_code == 200


def test_stt_explicitly_requires_worker(client, monkeypatch):
    monkeypatch.delenv("WHISPER_PYTHON", raising=False)
    result=client.post("/api/transcribe",files={"audio":("voice.wav",voice_sample(),"audio/wav")})
    assert result.status_code == 503


def test_transcription_real_job_pipeline_with_stubbed_worker(client, monkeypatch, tmp_path):
    monkeypatch.setattr(extras, "_stt_python", lambda: "/fake/python")
    def fake_execute(command, **kwargs):
        dest=Path(command[command.index("--output")+1])
        dest.write_text(json.dumps({"language":"ar","text":"هلا شلونك",
                      "segments":[{"start":0,"end":1,"text":"هلا شلونك"}]}),encoding="utf-8")
    monkeypatch.setattr(engines, "_execute", fake_execute)
    response=client.post("/api/transcribe",
            files={"audio":("sample.wav",voice_sample(),"audio/wav")},
            data={"language":"ar","model":"tiny"})
    assert response.status_code==202,response.text
    result=wait(client,response.json()["id"])
    assert result["status"]=="completed",result
    assert result["transcript"]["text"]=="هلا شلونك"


def test_voiceover_uses_saved_real_reference_with_engine_mock(client,monkeypatch):
    created=client.post("/api/voices",data={"name":"Own Voice","consent":"true"},
           files={"audio":("voice.wav",voice_sample(),"audio/wav")}).json()["voice"]["id"]
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    def assert_speech(**kwargs):
        assert kwargs["reference"].is_file()
        assert kwargs["text_file"].read_text()=="مرحبا"
        Path(kwargs["output"]).write_bytes(voice_sample())
    monkeypatch.setattr(engines,"synthesize",assert_speech)
    response=client.post("/api/voiceover",data={
        "text":"مرحبا","language":"ar","voice_id":created,"consent":"true"})
    assert response.status_code==202,response.text
    assert wait(client,response.json()["id"])["status"]=="completed"


def test_voiceover_no_engine_is_not_fake(client, monkeypatch):
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":False}])
    assert client.post("/api/voiceover",data={"text":"مرحبا","consent":"true"}).status_code==503


def test_provider_api_requires_local_configuration(client,monkeypatch):
    monkeypatch.delenv("TTS_WEBUI_URL",raising=False)
    response=client.post("/api/provider/speech",data={
        "text":"hi","provider":"tts-webui","language":"en","consent":"true"})
    assert response.status_code==503


@pytest.mark.parametrize("address", [
    "https://127.0.0.1:9880", "http://example.com:9880",
    "http://127.0.0.1:9880/secret", "http://username@127.0.0.1:9880",
    "http://127.0.0.1:9880?q=a"
])
def test_http_provider_blocks_nonloopback_or_unsafe_url(address,monkeypatch):
    monkeypatch.setenv("GPT_SOVITS_URL",address)
    assert providers.local_base_url("GPT_SOVITS_URL") is None


def test_http_provider_accepts_explicit_loopback_only(monkeypatch):
    monkeypatch.setenv("GPT_SOVITS_URL","http://127.0.0.1:9880")
    assert providers.local_base_url("GPT_SOVITS_URL")=="http://127.0.0.1:9880"


def test_provider_request_is_real_wav_output_when_local_adapter_responds(client,monkeypatch):
    monkeypatch.setenv("TTS_WEBUI_URL","http://localhost:7778")
    def fake_provider(**kwargs):
        assert kwargs["provider"]=="tts-webui"
        assert kwargs["text"]=="hello"
        Path(kwargs["output"]).write_bytes(voice_sample())
    monkeypatch.setattr(providers,"synthesize_provider",fake_provider)
    response=client.post("/api/provider/speech",
       data={"provider":"tts-webui","text":"hello","language":"en","consent":"true"})
    assert response.status_code==202,response.text
    result=wait(client,response.json()["id"])
    assert result["status"]=="completed"
    assert client.get(result["download"]).status_code==200
