"""Tests for actual upstream Applio CLI command construction; model weights are stubbed."""
from pathlib import Path
import json
import sys
import time
from types import SimpleNamespace
import wave

import pytest
from fastapi.testclient import TestClient
from studio import app as server, training


def write_wav(path: Path):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x01\x00" * 16000)


@pytest.fixture
def training_client(tmp_path, monkeypatch):
    root=tmp_path / "applio"
    root.mkdir()
    (root / "core.py").write_text("# official Applio CLI stub for tests")
    (root / "logs").mkdir()
    dataset=tmp_path / "dataset"
    dataset.mkdir()
    records=[]
    for index in range(10):
        file=f"clip_{index}.wav"
        write_wav(dataset/file)
        records.append({"audio":file,"text":"أهلا، اختبار مسجل.",
                        "speaker_id":"own_voice","language":"ar",
                        "consent":True,
                        "split":"train" if index < 6 else ("validation" if index < 8 else "test")})
    (dataset / "manifest.jsonl").write_text("\n".join(json.dumps(v,ensure_ascii=False) for v in records),encoding="utf-8")
    monkeypatch.setenv("APPLIO_ROOT", str(root))
    monkeypatch.setenv("APPLIO_PYTHON", sys.executable)
    monkeypatch.setenv("APPLIO_TRAIN_DATA", str(dataset))
    output_dir=tmp_path / "data"
    output_dir.mkdir()
    monkeypatch.setattr(server, "DATA", output_dir)
    with server.job_lock:
        server.jobs.clear()
    with TestClient(server.app) as client:
        yield client,root,dataset
    with server.job_lock:
        server.jobs.clear()


def poll_job(client, job_id):
    for _ in range(250):
        job=client.get("/api/jobs/"+job_id).json()
        if job["status"] in ("completed","failed"):
            return job
        time.sleep(.008)
    raise AssertionError("Training job did not finish in test")


def test_training_data_audit_gate(training_client):
    client,_,_=training_client
    readiness=client.get("/api/training/status")
    assert readiness.status_code==200
    assert readiness.json()["ready"] is True
    assert readiness.json()["clips"]==10
    status={x["id"]:x for x in client.get("/api/tools").json()["tools"]}
    assert status["training"]["ready"] is True


def test_training_requires_both_confirmations(training_client):
    client,_,_=training_client
    result=client.post("/api/train",data={"model_name":"Mina_001","consent":"true"})
    assert result.status_code==422


def test_training_rejects_invalid_hyperparams_and_names(training_client):
    client,_,_=training_client
    base={"model_name":"../unsafe","consent":"true","acknowledge":"true"}
    assert client.post("/api/train",data=base).status_code==422
    base["model_name"]="Mina_001"
    base["epochs"]="9001"
    assert client.post("/api/train",data=base).status_code==422


def test_training_invokes_real_upstream_three_stage_cli(training_client,monkeypatch):
    client,root,_=training_client
    observed=[]
    def fake_subprocess(args,**kwargs):
        observed.append(args)
        if args[2]=="train":
            directory=root/"logs"/"Mina_001"
            directory.mkdir()
            (directory/"G_10.pth").write_bytes(b"trained weights simulated in test")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(training.subprocess,"run",fake_subprocess)
    request=client.post("/api/train",data={
        "model_name":"Mina_001","epochs":"40","batch_size":"4",
        "gpu":"0","sample_rate":"40000","consent":"true","acknowledge":"true"})
    assert request.status_code==202,request.text
    job=poll_job(client,request.json()["id"])
    assert job["status"]=="completed",job
    assert [x[2] for x in observed]==["preprocess","extract","train"]
    assert job["training"]["checkpoint_count"]>=1
    assert client.get(f"/api/jobs/{job['id']}/training-log").status_code==200


def test_zero_cli_exit_without_checkpoint_is_not_marked_success(training_client,monkeypatch):
    client,_,_=training_client
    monkeypatch.setattr(training.subprocess,"run",lambda *args,**kw:SimpleNamespace(returncode=0))
    request=client.post("/api/train",data={
        "model_name":"Mina_002","consent":"true","acknowledge":"true"})
    assert request.status_code==202
    job=poll_job(client,request.json()["id"])
    assert job["status"]=="failed"
    assert "checkpoint" in job["error"].lower()


def test_existing_model_is_never_overwritten(training_client):
    client,root,_=training_client
    (root/"logs"/"Mina_001").mkdir()
    request=client.post("/api/train",data={
        "model_name":"Mina_001","consent":"true","acknowledge":"true"})
    assert request.status_code==409
