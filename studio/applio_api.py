"""Local-only API endpoints reusing Applio's actual core capabilities."""
from __future__ import annotations
from pathlib import Path
import shutil

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from studio import engines
from studio.applio_advanced import (
    batch_convert, blend_models, validate_settings, NEW_MODEL,
)

router = APIRouter(prefix="/api/applio")


def server():
    from studio import app
    return app


def _require_model(model_id: str) -> None:
    if not engines.applio_root():
        raise HTTPException(503, "Install Applio; set APPLIO_ROOT and APPLIO_PYTHON.")
    try:
        engines.resolve_model(model_id)
    except engines.EngineError as exc:
        raise HTTPException(422, str(exc)) from exc


def _settings(pitch, index_rate, protect, f0_method, autotune, cleanup, cleanup_strength):
    try:
        return validate_settings(pitch=pitch, index_rate=index_rate,
                                 protect=protect, f0_method=f0_method,
                                 autotune=autotune, cleanup=cleanup,
                                 cleanup_strength=cleanup_strength)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/capabilities")
def capabilities():
    catalog = engines.model_catalog()
    return {
        "installed": engines.applio_root() is not None,
        "model_count": len(catalog),
        "capabilities": {
            "single": True, "batch": True, "blender": True,
            "pitch": True, "autotune": True, "cleanup": True,
            "live_streaming": False,
        },
        "note": "Native Applio features require installed upstream runtime and model files; integration is not an audio-quality benchmark.",
    }


@router.post("/batch", status_code=202)
async def launch_batch(
    audio: list[UploadFile] = File(...),
    model_id: str = Form(...),
    pitch: int = Form(0),
    index_rate: float = Form(0.3),
    protect: float = Form(0.33),
    f0_method: str = Form("rmvpe"),
    autotune: bool = Form(False),
    cleanup: str = Form("off"),
    cleanup_strength: float = Form(12.0),
    consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "Confirm the speaker has authorized conversion.")
    if not 2 <= len(audio) <= 8:
        raise HTTPException(422, "Select between 2 and 8 audio files.")
    _require_model(model_id)
    opts = _settings(pitch, index_rate, protect, f0_method,
                     autotune, cleanup, cleanup_strength)
    host = server()
    job_id, directory = host._new_job("applio-batch")
    folder = directory / "batch-input"
    folder.mkdir()
    try:
        sources = []
        for i, upload in enumerate(audio):
            # Never trust filenames as paths; stable generated names avoid collisions.
            source = await host._save_audio(upload, folder / f"clip-{i+1:02}")
            sources.append(source)
    except Exception:
        host._discard_job(job_id)
        raise

    def work():
        host._record(job_id, status="running")
        try:
            archive = directory / "batch.zip"
            batch_convert(sources=sources, model_id=model_id, output=archive, settings=opts)
        except Exception as exc:
            host._record(job_id, status="failed", error=str(exc)[:800])
        else:
            host._record(job_id, status="completed",
                         download=f"/api/applio/jobs/{job_id}/archive")
    try:
        host.pool.submit(work)
    except RuntimeError as exc:
        host._discard_job(job_id)
        raise HTTPException(503, "Audio queue unavailable.") from exc
    return {"id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}/archive")
def batch_archive(job_id: str):
    host = server()
    with host.job_lock:
        record = host.jobs.get(job_id)
        if not record or record.get("engine") != "applio-batch" or record.get("status") != "completed":
            raise HTTPException(404, "Completed batch job not found")
    archive = host.DATA / job_id / "batch.zip"
    if not archive.is_file():
        raise HTTPException(404, "Batch ZIP was not produced")
    return FileResponse(archive, media_type="application/zip",
                        filename="mina-applio-batch.zip")


@router.post("/blend", status_code=202)
def blend(
    model_a: str = Form(...),
    model_b: str = Form(...),
    name: str = Form(...),
    ratio: float = Form(0.5),
    consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "You must have permission to combine these models.")
    if not NEW_MODEL.fullmatch(name) or not 0 <= ratio <= 1:
        raise HTTPException(422, "Invalid name or blending ratio.")
    if model_a == model_b:
        raise HTTPException(422, "Choose two different source models.")
    _require_model(model_a)
    _require_model(model_b)
    output = engines.applio_root() / "logs" / f"{name}.pth"
    if output.exists():
        raise HTTPException(409, "Output model name is already taken.")
    host = server()
    job_id, _ = host._new_job("applio-blend")

    def work():
        host._record(job_id, status="running")
        try:
            result = blend_models(first=model_a, second=model_b, name=name, ratio=ratio)
        except Exception as exc:
            host._record(job_id, status="failed", error=str(exc)[:800])
        else:
            host._record(job_id, status="completed", model=result)
    try:
        host.pool.submit(work)
    except RuntimeError as exc:
        host._discard_job(job_id)
        raise HTTPException(503, "Audio queue unavailable.") from exc
    return {"id": job_id, "status": "queued"}
