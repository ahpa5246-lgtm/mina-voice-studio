"""Test real reusable scripts and nondestructive line-repair against actual WAV data.

Only the expensive neural acoustic model is stubbed; HTTP, files, audio
resampling, project optimistic concurrency and ZIP assembly are exercised.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import time
import wave
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from studio import app as host, engines


def make_wav(value: int, rate: int = 16000) -> bytes:
    data = io.BytesIO()
    with wave.open(data, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(value.to_bytes(2, "little", signed=True) * int(rate * .2))
    return data.getvalue()


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "DATA", tmp_path)
    with host.job_lock:
        host.jobs.clear()
    with TestClient(host.app) as client:
        yield client
    with host.job_lock:
        host.jobs.clear()


def character(api, name):
    resp=api.post("/api/cast/characters",data={
        "name":name,"model":"multilingual-v3","language":"en","consent":"true"})
    assert resp.status_code==201, resp.text
    return resp.json()["character"]["id"]


def wait(api, identifier):
    for _ in range(250):
        job=api.get("/api/jobs/"+identifier).json()
        if job["status"] in ("completed","failed"):
            return job
        time.sleep(.01)
    pytest.fail("Audio processing queue did not settle")


def test_project_save_reopen_version_update_and_delete(api):
    a=character(api,"Hero")
    script=[{"character_id":a,"text":"A first sentence!","delivery":"neutral","pause_ms":100}]
    assert api.post("/api/cast/projects",json={"title":"   ","lines":script}).status_code==422
    created=api.post("/api/cast/projects",json={"title":"Pilot episode","lines":script})
    assert created.status_code==201,created.text
    saved=created.json()["project"]
    assert saved["version"]==1
    assert saved["lines"][0]["character_id"]==a
    assert len(api.get("/api/cast/projects").json()["projects"])==1
    path=host.DATA/"_projects"/(saved["id"]+".json")
    assert path.is_file()
    # Project files persist independently of per-request in-memory job state.
    with host.job_lock:host.jobs.clear()
    assert api.get("/api/cast/projects/"+saved["id"]).json()["project"]["title"]=="Pilot episode"
    changed=[{**script[0],"text":"Revised dialogue."}]
    updated=api.put("/api/cast/projects/"+saved["id"],json={
        "title":"Episode one v2","lines":changed,"expected_version":1})
    assert updated.status_code==200,updated.text
    assert updated.json()["project"]["version"]==2
    assert api.put("/api/cast/projects/"+saved["id"],json={
        "title":"Overwritten by stale tab","lines":script,"expected_version":1}).status_code==409
    assert api.get("/api/cast/projects/"+saved["id"]).json()["project"]["lines"]==changed
    assert api.put("/api/cast/projects/"+saved["id"],json={
        "title":"Bad","lines":[{**script[0],"character_id":"f"*32}],
        "expected_version":2}).status_code==422
    assert api.get("/api/cast/projects/"+saved["id"]).json()["project"]["version"]==2
    assert not list((host.DATA/"_projects").glob(".saving-*"))
    assert api.delete("/api/cast/projects/"+saved["id"]).status_code==200
    assert api.get("/api/cast/projects/"+saved["id"]).status_code==404
    assert api.get("/api/cast/characters").json()["characters"][0]["id"]==a


def test_revision_replaces_only_one_line_and_preserves_other_wavs(api,monkeypatch):
    first=character(api,"Shoko")
    second=character(api,"Robot")
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    seen=[]
    def synthesize(**kwargs):
        line=kwargs["text_file"].read_text(encoding="utf-8")
        seen.append(line)
        rate=24000 if kwargs["language"]=="en" and line.startswith("Robot") else 16000
        kwargs["output"].write_bytes(make_wav(700+len(seen)*100,rate=rate))
    monkeypatch.setattr(engines,"synthesize",synthesize)
    script=[
        {"character_id":first,"text":"Welcome to Frustration!","delivery":"neutral","pause_ms":200},
        {"character_id":second,"text":"Robot reports a problem.","delivery":"neutral","pause_ms":100},
        {"character_id":first,"text":"Oh no, not again!","delivery":"neutral","pause_ms":0},
    ]
    original=api.post("/api/cast/episodes",data={
        "script_json":json.dumps(script),"consent":"true"})
    assert original.status_code==202,original.text
    old_job=wait(api,original.json()["id"])
    assert old_job["status"]=="completed",old_job
    old_zip=api.get(old_job["archive"]).content
    old_audio=api.get(old_job["download"]).content
    replacement=api.post(f"/api/cast/episodes/{old_job['id']}/retry/2",
        data={"text":"Robot has completely malfunctioned.","delivery":"angry","consent":"true"})
    assert replacement.status_code==202,replacement.text
    new_job=wait(api,replacement.json()["id"])
    assert new_job["status"]=="completed",new_job
    assert new_job["revised_from"]==old_job["id"]
    assert new_job["revised_line"]==2
    assert len(seen)==4 and seen[-1]=="Robot has completely malfunctioned."
    with ZipFile(io.BytesIO(old_zip)) as z1, ZipFile(io.BytesIO(api.get(new_job["archive"]).content)) as z2:
        assert z1.read("lines/line-001.wav")==z2.read("lines/line-001.wav")
        assert z1.read("lines/line-003.wav")==z2.read("lines/line-003.wav")
        assert z1.read("lines/line-002.wav")!=z2.read("lines/line-002.wav")
        assert "Robot has completely malfunctioned" in z2.read("dialogue.srt").decode()
        assert "Robot reports a problem" in z1.read("dialogue.srt").decode()
        assert z2.read("manifest.json")!=z1.read("manifest.json")
        assert z2.read("episode.wav")!=z1.read("episode.wav")
    assert api.get(old_job["download"]).content==old_audio
    assert api.post(f"/api/cast/episodes/{old_job['id']}/retry/99",
                    data={"text":"x","consent":"true"}).status_code==422
    assert api.post(f"/api/cast/episodes/{old_job['id']}/retry/1",
                    data={"text":"not consented"}).status_code==422


def test_project_capacity_and_reference_validation(api):
    identifier=character(api,"Hero")
    script=[{"character_id":identifier,"text":"Hello","delivery":"neutral","pause_ms":0}]
    assert api.post("/api/cast/projects",json={"title":"Test","lines":[]}).status_code==422
    assert api.post("/api/cast/projects",json={
        "title":"Test","lines":[{"character_id":"a"*32,"text":"Wrong"}]}).status_code==422
    for n in range(40):
        result=api.post("/api/cast/projects",json={"title":f"Episode {n}","lines":script})
        assert result.status_code==201,result.text
    assert len(api.get("/api/cast/projects").json()["projects"])==40
    assert api.post("/api/cast/projects",json={"title":"Overflow","lines":script}).status_code==409


def test_optional_resampler_preserves_audio_length_and_level(tmp_path):
    from studio import cast
    def wav(path,rate,channels,val,seconds=.2):
        with wave.open(str(path),"wb") as f:
            f.setframerate(rate);f.setnchannels(channels);f.setsampwidth(2)
            f.writeframes(val.to_bytes(2,"little",signed=True)*int(rate*seconds)*channels)
    voice=cast.create_character(tmp_path,name="H")
    files=[tmp_path/"a.wav",tmp_path/"b.wav"]
    wav(files[0],24000,2,4000)
    wav(files[1],16000,1,4000)
    items=[{"character":voice,"text":"one","delivery":"neutral","pause_ms":0},
           {"character":voice,"text":"two","delivery":"neutral","pause_ms":0}]
    details=cast.assemble_episode(items,files,tmp_path)
    assert details["channels"]==2
    assert details["sample_rate"]==24000
    with wave.open(str(tmp_path/"output.wav"),"rb") as sample:
        assert 9400<sample.getnframes()<9800
        assert sample.getnchannels()==2
        audio=sample.readframes(sample.getnframes())
        import numpy as np
        pcm=np.frombuffer(audio,dtype="<i2")
        assert np.max(abs(pcm.astype("i4")))<7000
        assert 3500<np.mean(pcm[:int(24000*.2)*2])<4500
