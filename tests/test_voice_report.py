"""Real Qwen stdio health lifecycle and honest optional speaker-report endpoint."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import time
from fastapi.testclient import TestClient

from studio import app as server, qwen_runtime
from scripts import voice_consistency


def test_qwen_worker_reuses_same_private_pid_without_model_weights(monkeypatch,tmp_path):
    qwen_runtime.release()
    monkeypatch.setenv("QWEN_PYTHON",sys.executable)
    monkeypatch.setenv("MINA_DATA_DIR",str(tmp_path))
    try:
        assert qwen_runtime.request({"action":"ping"},timeout=10)["ok"]
        p=qwen_runtime._process.pid
        for _ in range(8):
            response=qwen_runtime.request({"action":"ping"},timeout=10)
            assert response["ok"]
            assert qwen_runtime._process.pid==p
    finally:
        qwen_runtime.release()
    assert qwen_runtime._process is None


def test_qwen_worker_reports_real_bad_mode_not_success(monkeypatch,tmp_path):
    qwen_runtime.release()
    monkeypatch.setenv("QWEN_PYTHON",sys.executable)
    monkeypatch.setenv("MINA_DATA_DIR",str(tmp_path))
    try:
        try:
            qwen_runtime.request({"mode":"nonexistent","text":"Hello",
                "output":str(tmp_path/"none.wav")},timeout=10)
            raise AssertionError("Unsupported mode must not be accepted")
        except RuntimeError as error:
            assert "Unsupported model mode" in str(error)
        assert not (tmp_path/"none.wav").exists()
    finally:
        qwen_runtime.release()


def test_optional_speaker_report_api_is_real_and_bounded(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    identifier="a"*32
    folder=tmp_path/identifier
    folder.mkdir()
    (folder/"episode.zip").write_bytes(b"stubbed zip for test")
    with server.job_lock:
        server.jobs.clear()
        server.jobs[identifier]={
            "id":identifier,"engine":"cartoon-episode","status":"completed",
            "updated":time.time(),"created":time.time()}
    real_find=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,"find_spec",
        lambda name: object() if name=="resemblyzer" else real_find(name))
    def fake_embedding(path):
        assert path==(folder/"episode.zip")
        return {"within_character_mean_cosine":.86,
                "between_character_mean_cosine":.4,"passed":None}
    monkeypatch.setattr(voice_consistency,"evaluate_archive",fake_embedding)
    with TestClient(server.app) as client:
        req=client.post(f"/api/cast/episodes/{identifier}/speaker-report")
        assert req.status_code==202,req.text
        job_id=req.json()["id"]
        for _ in range(200):
            result=client.get(f"/api/jobs/{job_id}").json()
            if result["status"] in {"completed","failed"}:break
            time.sleep(.01)
        assert result["status"]=="completed",result
        assert result["report"]["within_character_mean_cosine"]==.86
        assert result["report"]["passed"] is None
        assert client.post("/api/cast/episodes/"+("b"*32)+"/speaker-report").status_code==404
    with server.job_lock:server.jobs.clear()


def test_speaker_report_requires_actual_embedding_model(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    real_find=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,"find_spec",
        lambda name: None if name=="resemblyzer" else real_find(name))
    with TestClient(server.app) as client:
        result=client.post("/api/cast/episodes/"+("a"*32)+"/speaker-report")
    assert result.status_code==503


def test_speaker_report_ui_is_wired():
    root=Path(__file__).resolve().parents[1]
    html=(root/"studio/static/index.html").read_text(encoding="utf-8")
    js=(root/"studio/static/cast.js").read_text(encoding="utf-8")
    assert 'id="checkSpeaker"' in html and 'id="speakerReport"' in html
    assert "/speaker-report" in js
