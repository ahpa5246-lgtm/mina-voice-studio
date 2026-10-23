"""Cartoon voice-cast integration: real WAV assembly, script gating and HTTP."""
from __future__ import annotations
import io
import json
from pathlib import Path
from zipfile import ZipFile
import time
import wave

import pytest
from fastapi.testclient import TestClient
from studio import app as server, cast, engines


def wav_bytes(sample: int = 7, frames: int = 1600) -> bytes:
    out=io.BytesIO()
    with wave.open(out,"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(int(sample).to_bytes(2,"little",signed=True)*frames)
    return out.getvalue()


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    with server.job_lock:
        server.jobs.clear()
    with TestClient(server.app) as c:
        yield c
    with server.job_lock:
        server.jobs.clear()


def make_voice(c,name):
    response=c.post("/api/voices",data={"name":name,"consent":"true"},
        files={"audio":("own-voice.wav",wav_bytes(),"audio/wav")})
    assert response.status_code==201,response.text
    return response.json()["voice"]["id"]


def make_character(c,name,reference="",model="multilingual-v3",language="ar"):
    response=c.post("/api/cast/characters",data={
        "name":name,"voice_id":reference,"model":model,"language":language,
        "exaggeration":".5","cfg_weight":".5","consent":"true"})
    assert response.status_code==201,response.text
    return response.json()["character"]["id"]


def await_job(c,identifier):
    for _ in range(300):
        j=c.get("/api/jobs/"+identifier).json()
        if j["status"] in ("completed","failed"):return j
        time.sleep(.007)
    pytest.fail("Episode job did not finish")


def test_local_profiles_retain_unique_voice_links(client):
    a=make_voice(client,"Voice A")
    b=make_voice(client,"Voice B")
    x=make_character(client,"Hero",a)
    y=make_character(client,"Villain",b)
    profiles={v["id"]:v for v in client.get("/api/cast/characters").json()["characters"]}
    assert profiles[x]["voice_id"]==a
    assert profiles[y]["voice_id"]==b
    assert len(profiles)==2
    assert client.delete("/api/cast/characters/"+x).status_code==200
    assert client.get("/api/cast/characters").json()["characters"][0]["id"]==y
    assert client.delete("/api/cast/characters/"+x).status_code==404


def test_characters_require_permission_and_real_reference(client):
    assert client.post("/api/cast/characters",data={"name":"Unsafe"}).status_code==422
    assert client.post("/api/cast/characters",data={
        "name":"??","voice_id":"a"*32,"consent":"true"}).status_code==404
    assert client.post("/api/cast/characters",data={
        "name":"Nano Arabic","model":"nano","language":"ar","consent":"true"}).status_code==422
    assert client.post("/api/cast/characters",data={
        "name":"Turbo English","model":"turbo","language":"en","consent":"true"}).status_code==422


def test_real_episode_three_speakers_wav_srt_zip(client,monkeypatch):
    ids=[make_voice(client,f"Voice-{i}") for i in range(3)]
    profiles=[make_character(client,n,v) for n,v in zip(["Shoko","Robot","Professor"],ids)]
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    rendered=[]
    def fake_engine(*,text_file,output,reference,language,model,exaggeration,cfg_weight):
        assert reference is not None and reference.is_file()
        rendered.append((text_file.read_text(encoding="utf-8"),reference.parent.name,
                         exaggeration,cfg_weight))
        target=Path(output)
        index=len(rendered)
        target.write_bytes(wav_bytes(sample=index*800))
    monkeypatch.setattr(engines,"synthesize",fake_engine)
    lines=[
      {"character_id":profiles[0],"text":"مرحبا بكم!","delivery":"energetic","pause_ms":150},
      {"character_id":profiles[1],"text":"أنا روبوت.","delivery":"neutral","pause_ms":250},
      {"character_id":profiles[2],"text":"لنبدأ الآن.","delivery":"dramatic","pause_ms":0}
    ]
    result=client.post("/api/cast/episodes",data={
        "script_json":json.dumps(lines,ensure_ascii=False),"consent":"true"})
    assert result.status_code==202,result.text
    job=await_job(client,result.json()["id"])
    assert job["status"]=="completed",job
    assert len(rendered)==3
    assert len(set(speaker for _,speaker,_,_ in rendered))==3
    assert rendered[0][2]>.5 and rendered[2][2]>.5
    assert job["episode"]["duration_seconds"]==.7
    output=client.get(job["download"])
    assert output.status_code==200
    with wave.open(io.BytesIO(output.content),"rb") as reader:
        assert reader.getnframes()==11200
        assert reader.getframerate()==16000
    subtitles=client.get(job["captions"])
    assert subtitles.status_code==200
    assert "Shoko: مرحبا بكم!" in subtitles.text
    assert "00:00:00,250 --> 00:00:00,350" in subtitles.text
    archive=client.get(job["archive"])
    assert archive.status_code==200
    with ZipFile(io.BytesIO(archive.content)) as z:
        assert len(z.namelist())==6
        assert {"episode.wav","dialogue.srt","manifest.json"}<=set(z.namelist())
        manifest=json.loads(z.read("manifest.json"))
        assert manifest["lines"][1]["character"]=="Robot"
        assert z.read("lines/line-003.wav")==wav_bytes(sample=2400)


def test_missing_speech_engine_reports_503(client,monkeypatch):
    p=make_character(client,"Default")
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":False}])
    result=client.post("/api/cast/episodes",data={
        "script_json":json.dumps([{"character_id":p,"text":"Hello"}]),"consent":"true"})
    assert result.status_code==503


def test_real_engine_failure_never_publishes_episode(client,monkeypatch):
    p=make_character(client,"Default")
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    def fail(**kwargs):
        raise RuntimeError("Model weights not available")
    monkeypatch.setattr(engines,"synthesize",fail)
    response=client.post("/api/cast/episodes",data={
        "script_json":json.dumps([{"character_id":p,"text":"مقطع أول"}]),"consent":"true"})
    job=await_job(client,response.json()["id"])
    assert job["status"]=="failed"
    assert "weights" in job["error"]
    assert client.get(f"/api/cast/episodes/{job['id']}/archive").status_code==404
    assert client.get(f"/api/jobs/{job['id']}/audio").status_code==404


@pytest.mark.parametrize("entry",[
    {"character_id":"missing","text":"missing ID"},
    {"character_id":"x"*32,"text":"Hi"},
    {"text":"","delivery":"neutral"},
    {"text":"Hello","delivery":"very_angry"},
    {"text":"Hello","pause_ms":5000},
    {"text":"Hello","pause_ms":True},
    {"text":"a"*501},
])
def test_script_rejects_invalid_lines(tmp_path,entry):
    profile=cast.create_character(tmp_path,name="Test")
    entry={"character_id":profile["id"],**entry}
    with pytest.raises(ValueError):
        cast.validate_script(tmp_path,[entry])


def test_script_limits_and_default_identity_warning(client):
    profile=make_character(client,"A character without unique timbre")
    result=client.get("/api/cast/characters").json()
    assert "distinct" in result["note"]
    entry={"character_id":profile,"text":"Hello"}
    assert client.post("/api/cast/episodes",data={
        "script_json":json.dumps([entry]*49),"consent":"true"}).status_code in (422,503)
    with pytest.raises(ValueError):
        cast.validate_script(server.DATA,[entry]*49)
    with pytest.raises(ValueError):
        cast.validate_script(server.DATA,[dict(entry,text="a"*501)])
    assert client.get("/api/cast/episodes/"+("a"*32)+"/archive").status_code==404


def test_episode_requires_consent(client,monkeypatch):
    profile=make_character(client,"Test")
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    response=client.post("/api/cast/episodes",data={
        "script_json":json.dumps([{"character_id":profile,"text":"Hello"}])})
    assert response.status_code==422


def test_sample_rate_mismatch_is_explicit_failure(tmp_path):
    profile=cast.create_character(tmp_path,name="Test")
    a=tmp_path/"a.wav";b=tmp_path/"b.wav"
    a.write_bytes(wav_bytes())
    with wave.open(str(b),"wb") as writer:
        writer.setnchannels(1);writer.setsampwidth(2);writer.setframerate(22050)
        writer.writeframes(b"\x00\x01"*2205)
    lines=[{"character":profile,"text":"one","delivery":"neutral","pause_ms":250},
           {"character":profile,"text":"two","delivery":"neutral","pause_ms":0}]
    with pytest.raises(ValueError,match="incompatible sample rates"):
        cast.assemble_episode(lines,[a,b],tmp_path)
