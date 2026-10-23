"""Qwen VoiceDesign / clone / acted preset integration without pretending GPU ran."""
import io
import json
import time
from pathlib import Path
import wave
from fastapi.testclient import TestClient
import pytest

from studio import app as server, engines, qwen_runtime, cast

def wav_bytes(rate=24000):
    stream=io.BytesIO()
    with wave.open(stream,"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(b"\x10\x00" * int(rate*.45))
    return stream.getvalue()

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    with server.job_lock:server.jobs.clear()
    with TestClient(server.app) as c:yield c
    with server.job_lock:server.jobs.clear()

def poll(c,job):
    for _ in range(500):
        res=c.get("/api/jobs/"+job).json()
        if res["status"] in ("completed","failed"):return res
        time.sleep(.006)
    pytest.fail("Job did not finish")

def test_design_requires_qwen_installation(client,monkeypatch):
    monkeypatch.setattr(qwen_runtime,"configured",lambda:False)
    res=client.post("/api/qwen/design",data={
        "name":"Shoko","description":"A bright young female voice with a sarcastic edge",
        "seed_text":"Seriously? This is happening right now!",
        "language":"English","consent":"true"})
    assert res.status_code==503
    assert client.get("/api/voices").json()["voices"]==[]

def test_design_creates_real_wav_reference_and_seed_transcript(client,monkeypatch):
    monkeypatch.setattr(qwen_runtime,"configured",lambda:True)
    observed=[]
    def synthesis(**kwargs):
        observed.append(kwargs)
        Path(kwargs["output"]).write_bytes(wav_bytes())
    monkeypatch.setattr(qwen_runtime,"synthesize",synthesis)
    request=client.post("/api/qwen/design",data={
        "name":"Shoko","description":"Young expressive actor with sarcastic delivery",
        "seed_text":"Okay, this is the weirdest day of my life.",
        "language":"English","consent":"true"})
    assert request.status_code==202,request.text
    job=poll(client,request.json()["id"])
    assert job["status"]=="completed",job
    assert len(observed)==1 and observed[0]["mode"]=="design"
    assert observed[0]["instruct"].startswith("Young")
    voice=job["voice"]
    assert voice["origin"]=="qwen-design"
    assert voice["seed_text"].startswith("Okay")
    library=client.get("/api/voices").json()["voices"]
    assert library[0]["id"]==voice["id"]
    assert client.get("/api/voices/"+voice["id"]+"/audio").content==wav_bytes()
    character=client.post("/api/cast/characters",data={
        "name":"Shoko","voice_id":voice["id"],"model":"qwen-clone",
        "language":"en","consent":"true"})
    assert character.status_code==201,character.text
    assert character.json()["character"]["reference_text"]==voice["seed_text"]

def test_design_failed_model_writes_no_voice_profile(client,monkeypatch):
    monkeypatch.setattr(qwen_runtime,"configured",lambda:True)
    def broken(**kwargs):raise RuntimeError("Model download failed")
    monkeypatch.setattr(qwen_runtime,"synthesize",broken)
    request=client.post("/api/qwen/design",data={
        "name":"Failed","description":"A very expressive character voice",
        "seed_text":"What just happened in this room?","consent":"true"})
    result=poll(client,request.json()["id"])
    assert result["status"]=="failed"
    assert client.get("/api/voices").json()["voices"]==[]

def test_qwen_clone_reuses_exact_reference_and_preset_style(client,monkeypatch):
    monkeypatch.setattr(qwen_runtime,"configured",lambda:True)
    first=client.post("/api/voices",data={"name":"My Own Voice","consent":"true"},
        files={"audio":("recording.wav",wav_bytes(),"audio/wav")}).json()["voice"]["id"]
    a=client.post("/api/cast/characters",data={
        "name":"Designed","voice_id":first,"model":"qwen-clone","language":"en",
        "reference_text":"This is the exact transcript.","consent":"true"})
    b=client.post("/api/cast/characters",data={
        "name":"Fixed actor","model":"qwen-custom","speaker":"Ryan",
        "language":"en","consent":"true"})
    assert a.status_code==201 and b.status_code==201,(a.text,b.text)
    cid=a.json()["character"]["id"]
    sid=b.json()["character"]["id"]
    seen=[]
    def generator(**kw):
        seen.append(kw)
        Path(kw["output"]).write_bytes(wav_bytes(rate=16000 if kw["mode"]=="custom" else 24000))
    monkeypatch.setattr(qwen_runtime,"synthesize",generator)
    lines=[
        {"character_id":cid,"text":"First line","delivery":"sarcastic","pause_ms":50},
        {"character_id":sid,"text":"Second line","delivery":"angry","pause_ms":50},
        {"character_id":cid,"text":"Third line","delivery":"crying","pause_ms":0},
    ]
    response=client.post("/api/cast/episodes",data={
        "script_json":json.dumps(lines),"consent":"true"})
    assert response.status_code==202,response.text
    done=poll(client,response.json()["id"])
    assert done["status"]=="completed",done
    assert [v["mode"] for v in seen]==["clone","custom","clone"]
    assert seen[0]["ref_text"]=="This is the exact transcript."
    assert seen[0]["ref_audio"]==seen[2]["ref_audio"]
    assert seen[0]["instruct"]==seen[2]["instruct"]==""  # Qwen Base has no per-line style
    assert "anger" in seen[1]["instruct"]
    with wave.open(io.BytesIO(client.get(done["download"]).content),"rb") as wav:
        assert wav.getframerate()==24000
        assert wav.getnframes()>32000  # includes resampled 16k speaker segment

def test_qwen_voice_cannot_claim_arabic_support(client):
    result=client.post("/api/cast/characters",data={
        "name":"Arabic Qwen","model":"qwen-custom","speaker":"Ryan",
        "language":"ar","consent":"true"})
    assert result.status_code==422
    assert "Arabic" in result.text

def test_qwen_clone_needs_exact_transcript(client):
    voice=client.post("/api/voices",data={"name":"Original","consent":"true"},
        files={"audio":("original.wav",wav_bytes(),"audio/wav")}).json()["voice"]["id"]
    result=client.post("/api/cast/characters",data={
        "name":"Clone","model":"qwen-clone","voice_id":voice,
        "language":"en","consent":"true"})
    assert result.status_code==422

def test_profile_limits_and_emotions(tmp_path):
    c=cast.create_character(tmp_path,name="Pretend")
    for mood in ("sad","angry","crying","sarcastic"):
        assert cast.validate_script(tmp_path,[{
            "character_id":c["id"],"text":"Hello","delivery":mood}])[0]["delivery"]==mood
    with pytest.raises(ValueError):
        cast.create_character(tmp_path,name="Wrong",model="qwen-custom",language="ar")
