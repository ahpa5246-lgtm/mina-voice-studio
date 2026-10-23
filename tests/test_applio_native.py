"""Native Applio integrations: actual WAV/ZIP handling and explicit mocked upstream CLI.

These tests do not claim acoustic quality or model training has run on a GPU.
"""
from __future__ import annotations
import io
from pathlib import Path
import sys
import time
import types
import wave
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from studio import app as server, engines
from studio import applio_advanced
from scripts import applio_native_worker


def wav_bytes():
    f = io.BytesIO()
    with wave.open(f, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x10" * 400)
    return f.getvalue()


@pytest.fixture()
def setup_applio(tmp_path, monkeypatch):
    root = tmp_path / "applio"
    root.mkdir()
    (root / "core.py").write_text("# controlled upstream stub")
    (root / "logs").mkdir()
    first = root / "logs" / "voice-one.pth"
    second = root / "logs" / "voice-two.pth"
    first.write_bytes(b"M" * 256)
    second.write_bytes(b"N" * 256)
    monkeypatch.setenv("APPLIO_ROOT", str(root))
    monkeypatch.setenv("APPLIO_PYTHON", sys.executable)
    monkeypatch.setattr(server, "DATA", tmp_path / "data")
    server.DATA.mkdir()
    with server.job_lock:
        server.jobs.clear()
    with TestClient(server.app) as client:
        yield client, root
    with server.job_lock:
        server.jobs.clear()


def await_job(client, identifier):
    for _ in range(300):
        result = client.get(f"/api/jobs/{identifier}").json()
        if result["status"] in {"failed", "completed"}:
            return result
        time.sleep(.005)
    pytest.fail("Applio job timed out in test")


def test_settings_enforce_safe_values():
    assert applio_advanced.validate_settings(pitch=-12)["pitch"] == -12
    for settings in ({"pitch": -25}, {"index_rate": 1.2}, {"protect": 0.9},
                     {"cleanup": "unsafe"}, {"cleanup_strength": 40},
                     {"f0_method": "unknown"}):
        with pytest.raises(ValueError):
            applio_advanced.validate_settings(**settings)


def test_native_worker_passes_upstream_required_embedding_argument(tmp_path, monkeypatch):
    root = tmp_path / "applio"
    root.mkdir()
    (root / "core.py").write_text("# test stub")
    source, output, model = (tmp_path / filename for filename in ["input.wav", "output.wav", "model.pth"])
    source.write_bytes(wav_bytes())
    model.write_bytes(b"model")
    def original_signature_stub(*, pitch, index_rate, volume_envelope,
                                protect, f0_method, input_path, output_path,
                                pth_path, index_path, f0_autotune,
                                f0_autotune_strength, proposed_pitch,
                                proposed_pitch_threshold, export_format,
                                embedder_model, **other):
        assert embedder_model == "contentvec"  # mandatory in upstream Applio
        assert other["cleanup_mode"] == "light"
        assert pitch == -3
        output.write_bytes(wav_bytes())
        return "Converted", str(output)
    monkeypatch.setitem(sys.modules, "core", types.SimpleNamespace(run_infer_script=original_signature_stub))
    monkeypatch.setattr(sys, "argv", [
        "applio_native_worker", "infer", "--root", str(root),
        "--model", str(model), "--input", str(source), "--output", str(output),
        "--pitch", "-3", "--cleanup", "light",
    ])
    applio_native_worker.main()
    assert output.read_bytes() == wav_bytes()


def test_conversion_parameters_reach_worker(setup_applio, monkeypatch):
    client, root = setup_applio
    seen = []
    def stub_execute(argv, **kwargs):
        seen.append(argv)
        dest = Path(argv[argv.index("--output") + 1])
        dest.write_bytes(wav_bytes())
    monkeypatch.setattr(engines, "_execute", stub_execute)
    request=client.post("/api/convert",data={
        "model_id":"voice-one.pth","consent":"true","pitch":"-4",
        "index_rate":".25","f0_method":"fcpe","autotune":"true",
        "cleanup":"light","cleanup_strength":"18"},
        files={"audio":("input.wav",wav_bytes(),"audio/wav")})
    assert request.status_code == 202, request.text
    result = await_job(client, request.json()["id"])
    assert result["status"] == "completed", result
    argv=seen[0]
    assert argv[argv.index("--pitch")+1] == "-4"
    assert argv[argv.index("--cleanup")+1] == "light"
    assert "--autotune" in argv
    assert argv[argv.index("--f0-method")+1] == "fcpe"
    assert client.get(result["download"]).content[:4] == b"RIFF"


def test_batch_conversion_generates_valid_zip(setup_applio, monkeypatch):
    client, root=setup_applio
    def stub_execute(argv, **kwargs):
        target=Path(argv[argv.index("--output-dir")+1])
        target.mkdir(exist_ok=True)
        for name in ["clip-01.wav","clip-02.wav"]:
            (target/name).write_bytes(wav_bytes())
    monkeypatch.setattr(engines, "_execute",stub_execute)
    request=client.post("/api/applio/batch",
        data={"model_id":"voice-one.pth","consent":"true"},
        files=[("audio",("alpha.wav",wav_bytes(),"audio/wav")),
               ("audio",("beta.wav",wav_bytes(),"audio/wav"))])
    assert request.status_code == 202, request.text
    result=await_job(client, request.json()["id"])
    assert result["status"]=="completed", result
    artifact=client.get(result["download"])
    assert artifact.status_code==200
    with ZipFile(io.BytesIO(artifact.content)) as archive:
        assert sorted(archive.namelist())==["clip-01.wav","clip-02.wav"]
        assert archive.read("clip-01.wav") == wav_bytes()


def test_batch_requires_two_and_consent(setup_applio):
    client, root=setup_applio
    one=[("audio",("one.wav",wav_bytes(),"audio/wav"))]
    assert client.post("/api/applio/batch",data={"model_id":"voice-one.pth","consent":"true"},files=one).status_code==422
    two=one+one
    assert client.post("/api/applio/batch",data={"model_id":"voice-one.pth"},files=two).status_code==422


def test_batch_fails_without_all_expected_wav_files(setup_applio,monkeypatch):
    client, root=setup_applio
    monkeypatch.setattr(engines,"_execute",lambda argv,**kw: None)
    request=client.post("/api/applio/batch",data={"model_id":"voice-one.pth","consent":"true"},files=[
        ("audio",("a.wav",wav_bytes(),"audio/wav")),
        ("audio",("b.wav",wav_bytes(),"audio/wav"))])
    result=await_job(client,request.json()["id"])
    assert result["status"]=="failed"
    assert client.get(f"/api/applio/jobs/{result['id']}/archive").status_code==404


def test_blend_models_returns_real_path_and_is_available_in_catalog(setup_applio, monkeypatch):
    client, root=setup_applio
    def fake_execute(argv, **kwargs):
        filename=argv[argv.index("--name")+1]
        (root/"logs"/(filename+".pth")).write_bytes(b"P"*256)
    monkeypatch.setattr(engines, "_execute", fake_execute)
    response=client.post("/api/applio/blend",data={
        "model_a":"voice-one.pth","model_b":"voice-two.pth",
        "name":"MergedVoice_01","ratio":".6","consent":"true"})
    assert response.status_code==202, response.text
    result=await_job(client,response.json()["id"])
    assert result["status"]=="completed", result
    assert result["model"]["model_id"]=="MergedVoice_01.pth"
    assert any(item["id"]=="MergedVoice_01.pth" for item in client.get("/api/models").json()["applio"])


def test_blend_prevents_overwrite_and_same_source(setup_applio):
    client,root=setup_applio
    fields={"model_a":"voice-one.pth","model_b":"voice-two.pth","name":"ExistingVoice","consent":"true"}
    (root/"logs"/"ExistingVoice.pth").write_bytes(b"X"*256)
    assert client.post("/api/applio/blend",data=fields).status_code==409
    fields["name"]="NewModelX"
    fields["model_b"]="voice-one.pth"
    assert client.post("/api/applio/blend",data=fields).status_code==422


def test_blend_error_does_not_falsely_report_success(setup_applio,monkeypatch):
    client,root=setup_applio
    monkeypatch.setattr(engines,"_execute",lambda argv,**kw:None)
    request=client.post("/api/applio/blend",data={
        "model_a":"voice-one.pth","model_b":"voice-two.pth","name":"NoOutput",
        "consent":"true"})
    job=await_job(client,request.json()["id"])
    assert job["status"]=="failed"


def test_browser_reports_native_capabilities_without_claiming_live_support(setup_applio):
    client,_=setup_applio
    result=client.get("/api/applio/capabilities").json()
    assert result["model_count"]==2
    assert result["capabilities"]["batch"] is True
    assert result["capabilities"]["live_streaming"] is False
