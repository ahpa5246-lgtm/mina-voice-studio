"""Tests for the private reusable Chatterbox worker and model guards."""
import sys
import pytest
from fastapi.testclient import TestClient
from studio import app as server, engines, chatterbox_runtime

def test_private_stdio_worker_reuses_pid_across_20_requests():
    chatterbox_runtime.release()
    try:
        assert chatterbox_runtime.request({"operation":"ping"},python=sys.executable,timeout=15)["ok"]
        pid=chatterbox_runtime.status()["pid"]
        assert pid
        for _ in range(20):
            assert chatterbox_runtime.request({"operation":"ping"},python=sys.executable,timeout=15)["ok"]
            assert chatterbox_runtime.status()["pid"]==pid
    finally:
        chatterbox_runtime.release()
    assert not chatterbox_runtime.status()["worker_running"]

def test_unsupported_worker_message_is_rejected():
    with pytest.raises(ValueError):
        chatterbox_runtime.request({"operation":"unsupported"})

@pytest.mark.parametrize("model,language",[
    ("turbo","en"),("nano","en"),("turbo","ar"),("nano","ar")])
def test_fast_models_require_reference(model,language,monkeypatch,tmp_path):
    monkeypatch.setattr(server,"DATA",tmp_path)
    monkeypatch.setattr(engines,"status",lambda:[{"id":"chatterbox","configured":True}])
    with TestClient(server.app) as client:
        response=client.post("/api/speech",data={
            "text":"Hello","model":model,"language":language,"consent":"true"})
    assert response.status_code==422

def test_chatterbox_presence_checks_installed_python(monkeypatch):
    monkeypatch.setenv("CHATTERBOX_PYTHON",sys.executable)
    monkeypatch.setattr(engines,"_module_installed",lambda *a,**kw:False)
    chatterbox=[v for v in engines.status() if v["id"]=="chatterbox"][0]
    assert chatterbox["configured"] is False

def test_active_job_blocks_model_unload(monkeypatch,tmp_path):
    monkeypatch.setattr(server,"DATA",tmp_path)
    with server.job_lock:
        server.jobs.clear()
        server.jobs["active"]={"engine":"chatterbox","status":"running"}
    try:
        with TestClient(server.app) as client:
            assert client.post("/api/runtime/chatterbox/unload").status_code==409
    finally:
        with server.job_lock:server.jobs.clear()
