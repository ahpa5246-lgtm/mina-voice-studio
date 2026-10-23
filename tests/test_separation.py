"""Integration tests of real Demucs command and stem validation using a CLI stub."""
from __future__ import annotations
import io
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import wave

import pytest
from fastapi.testclient import TestClient
from studio import app as server, separation


def wav_bytes():
    buf=io.BytesIO()
    with wave.open(buf,"wb") as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000)
        output.writeframes(b"\x10\x00"*1600)
    return buf.getvalue()

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    with server.job_lock:server.jobs.clear()
    with TestClient(server.app) as c:yield c
    with server.job_lock:server.jobs.clear()

def finish(client,identifier):
    import time
    for _ in range(1000):
        result=client.get("/api/jobs/"+identifier).json()
        if result["status"] in ("completed","failed"):return result
        time.sleep(.005)
    pytest.fail("Demucs job did not finish")

def test_demucs_requires_installed_upstream(client,monkeypatch):
    monkeypatch.setattr(separation,"installed",lambda:False)
    response=client.post("/api/separate",data={"consent":"true"},
        files={"audio":("sample.wav",wav_bytes(),"audio/wav")})
    assert response.status_code==503
    assert client.get("/api/tools").json()["tools"][0]["ready"] is False

def test_demucs_requires_audio_permission(client,monkeypatch):
    monkeypatch.setattr(separation,"installed",lambda:True)
    response=client.post("/api/separate",files={
        "audio":("sample.wav",wav_bytes(),"audio/wav")})
    assert response.status_code==422

def test_real_command_and_zip_artifact(client,monkeypatch):
    monkeypatch.setattr(separation,"installed",lambda:True)
    seen=[]
    def cli_stub(args,**kwargs):
        seen.append(args)
        folder=Path(args[args.index("-o")+1])/"htdemucs"/Path(args[-1]).stem
        folder.mkdir(parents=True)
        (folder/"vocals.wav").write_bytes(wav_bytes())
        (folder/"no_vocals.wav").write_bytes(wav_bytes())
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(separation.subprocess,"run",cli_stub)
    response=client.post("/api/separate",data={"consent":"true"},
        files={"audio":("sample.wav",wav_bytes(),"audio/wav")})
    assert response.status_code==202,response.text
    state=finish(client,response.json()["id"])
    assert state["status"]=="completed",state
    assert seen[0][2:4]==["demucs","--two-stems"]
    archive=client.get(state["download"])
    assert archive.status_code==200
    with ZipFile(io.BytesIO(archive.content)) as files:
        assert sorted(files.namelist())==["instrumental.wav","vocals.wav"]
        assert files.read("vocals.wav")==wav_bytes()

def test_zero_exit_without_stems_is_failure(client,monkeypatch):
    monkeypatch.setattr(separation,"installed",lambda:True)
    monkeypatch.setattr(separation.subprocess,"run",lambda *a,**k:SimpleNamespace(returncode=0))
    response=client.post("/api/separate",data={"consent":"true"},
        files={"audio":("sample.wav",wav_bytes(),"audio/wav")})
    state=finish(client,response.json()["id"])
    assert state["status"]=="failed"
    assert client.get("/api/separation/"+state["id"]+"/archive").status_code==404
