"""Cartoon voice cast and episode export API on the existing local-only server."""
from __future__ import annotations
import json
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse
from studio import cast, engines, qwen_runtime

router = APIRouter(prefix="/api/cast", tags=["cartoon-studio"])


def _server():
    from studio import app as server
    return server


def _reference(identifier: str) -> Path:
    from studio.extras import _voice_file
    return _voice_file(identifier)


@router.get("/characters")
def characters():
    host = _server()
    return {"characters": cast.all_characters(host.DATA),
            "limit": cast.MAX_CHARACTERS,
            "note": "A profile without a unique audio reference does not create a distinct voice identity."}


@router.post("/characters", status_code=201)
def create(
    name: str = Form(...), voice_id: str = Form(""),
    model: str = Form("multilingual-v3"), language: str = Form("ar"),
    exaggeration: float = Form(0.5), cfg_weight: float = Form(0.5),
    speaker: str = Form("Ryan"), reference_text: str = Form(""),
    consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "Confirm authorization to reuse the voice for this character.")
    if model == "qwen-clone" and voice_id and not reference_text.strip():
        from studio.extras import _metadata
        record = _metadata(_reference(voice_id).parent)
        if record and record.get("origin") == "qwen-design":
            reference_text = record.get("seed_text","")
    try:
        options = cast.validate_character(
            name, voice_id, model, language, exaggeration, cfg_weight,
            speaker, reference_text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if voice_id:
        _reference(voice_id)
    host = _server()
    try:
        profile = cast.create_character(host.DATA, **options)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"character": profile}


@router.delete("/characters/{character_id}")
def delete(character_id: str):
    try:
        cast.delete_character(_server().DATA, character_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"deleted": True}


@router.post("/episodes", status_code=202)
def produce_episode(script_json: str = Form(...), consent: bool = Form(False)):
    if not consent:
        raise HTTPException(422, "Confirm permission to synthesize these characters.")
    if len(script_json) > 18000:
        raise HTTPException(413, "Episode script exceeds input-size limit.")
    host = _server()
    try:
        raw = json.loads(script_json)
        script = cast.validate_script(host.DATA, raw)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    needs_chat = any(not item["character"]["model"].startswith("qwen-") for item in script)
    needs_qwen = any(item["character"]["model"].startswith("qwen-") for item in script)
    if needs_chat and not any(e["id"]=="chatterbox" and e["configured"] for e in engines.status()):
        raise HTTPException(503, "Install Chatterbox for the selected characters.")
    if needs_qwen and not qwen_runtime.configured():
        raise HTTPException(503, "Install qwen-tts and set QWEN_PYTHON for Qwen characters.")
    # Fail fast on dangling recorded-voice references.
    for line in script:
        voice_id = line["character"]["voice_id"]
        if voice_id:
            _reference(voice_id)
    job_id, directory = host._new_job("cartoon-episode")
    def process():
        host._record(job_id, status="running", current_line=0,
                     total_lines=len(script))
        try:
            episode = cast.render_episode(
                host.DATA, directory, script, _reference,
                lambda current, total: host._record(
                    job_id, current_line=current, total_lines=total))
            host._validate_output(directory / "output.wav")
        except Exception as exc:
            host._record(job_id, status="failed", error=str(exc)[:800])
        else:
            host._record(
                job_id, status="completed", episode=episode,
                download=f"/api/jobs/{job_id}/audio",
                archive=f"/api/cast/episodes/{job_id}/archive",
                captions=f"/api/cast/episodes/{job_id}/captions")
    try:
        host.pool.submit(process)
    except RuntimeError as exc:
        host._discard_job(job_id)
        raise HTTPException(503, "Processing queue unavailable.") from exc
    return {"id": job_id, "status": "queued", "lines": len(script)}


def _artifact(job_id: str, name: str) -> Path:
    host = _server()
    with host.job_lock:
        job = host.jobs.get(job_id)
        if not job or job.get("engine") != "cartoon-episode" or job.get("status") != "completed":
            raise HTTPException(404, "Completed episode not found.")
    file = host.DATA / job_id / name
    if not file.is_file():
        raise HTTPException(404, "Generated artifact not available.")
    return file


@router.get("/episodes/{job_id}/archive")
def archive(job_id: str):
    return FileResponse(_artifact(job_id, "episode.zip"),
                        media_type="application/zip",
                        filename=f"mina-cartoon-{job_id[:8]}.zip")


@router.get("/episodes/{job_id}/captions")
def captions(job_id: str):
    return FileResponse(_artifact(job_id, "dialogue.srt"),
                        media_type="text/plain; charset=utf-8",
                        filename=f"mina-cartoon-{job_id[:8]}.srt")
