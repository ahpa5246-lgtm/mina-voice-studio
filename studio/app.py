"""Local FastAPI application, upload limits and sequential GPU job queue."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from studio import engines

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("MINA_DATA_DIR", str(ROOT / "data"))).expanduser().resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
LANGUAGES = {"ar", "en", "fr", "es", "de", "it", "pt", "hi", "ja", "zh"}

app = FastAPI(title="Mina Voice Studio", version="0.1.0", docs_url="/api/docs", redoc_url=None)
app.mount("/assets", StaticFiles(directory=str(ROOT / "studio" / "static")), name="assets")
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mina-audio")
jobs: dict[str, dict] = {}
job_lock = threading.Lock()


def _record(job_id: str, **changes) -> None:
    with job_lock:
        jobs[job_id].update(changes)


def _schedule(operation, job_id: str, **kwargs) -> None:
    def work():
        _record(job_id, status="running")
        try:
            operation(**kwargs)
        except Exception as exc:
            _record(job_id, status="failed", error=str(exc)[:1800])
        else:
            _record(job_id, status="completed", download="/api/jobs/" + job_id + "/audio")
    pool.submit(work)


def _new_job(engine: str) -> tuple[str, Path]:
    job_id = uuid4().hex
    directory = DATA / job_id
    directory.mkdir(parents=True, exist_ok=False)
    with job_lock:
        jobs[job_id] = {
            "id": job_id,
            "engine": engine,
            "status": "queued",
            "created": int(time.time()),
            "download": None,
            "error": None,
        }
    return job_id, directory


async def _save_audio(upload: UploadFile, destination: Path) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(422, "Please upload WAV, MP3, FLAC, OGG or M4A audio.")
    path = destination.with_suffix(suffix)
    amount = 0
    try:
        with path.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                amount += len(chunk)
                if amount > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Audio file exceeds the 25 MB limit.")
                stream.write(chunk)
        if amount < 44:
            raise HTTPException(422, "The audio file is empty or too small.")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return path


def _configured(engine_id: str) -> bool:
    return any(e["id"] == engine_id and e["configured"] for e in engines.status())


@app.get("/")
def home():
    return FileResponse(ROOT / "studio" / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"version": app.version, "local_only_default": True, "engines": engines.status()}


@app.get("/api/models")
def models():
    return {"applio": engines.model_catalog()}


@app.post("/api/speech", status_code=202)
async def make_speech(
    text: str = Form(...),
    language: str = Form("ar"),
    consent: bool = Form(False),
    reference: UploadFile | None = File(None),
    exaggeration: float = Form(0.5),
    cfg_weight: float = Form(0.5),
):
    if not consent:
        raise HTTPException(422, "Confirm that you have permission to use the reference voice.")
    text = text.strip()
    if not 1 <= len(text) <= 300:
        raise HTTPException(422, "Text must contain 1–300 characters per generation.")
    if language not in LANGUAGES:
        raise HTTPException(422, "Unsupported language.")
    if not 0.25 <= exaggeration <= 1.0 or not 0.0 <= cfg_weight <= 1.0:
        raise HTTPException(422, "Invalid voice settings.")
    if not _configured("chatterbox"):
        raise HTTPException(503, "Chatterbox has not been installed/configured.")
    job_id, directory = _new_job("chatterbox")
    text_file = directory / "text.txt"
    text_file.write_text(text, encoding="utf-8")
    try:
        reference_path = await _save_audio(reference, directory / "reference") if reference else None
    except Exception:
        with job_lock:
            jobs.pop(job_id, None)
        raise
    _schedule(
        engines.synthesize,
        job_id,
        text_file=text_file,
        reference=reference_path,
        language=language,
        output=directory / "output.wav",
        exaggeration=exaggeration,
        cfg_weight=cfg_weight,
    )
    return {"id": job_id, "status": "queued"}


@app.post("/api/convert", status_code=202)
async def make_conversion(
    audio: UploadFile = File(...),
    model_id: str = Form(...),
    consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "Confirm that you have permission to use this voice.")
    if not _configured("applio"):
        raise HTTPException(503, "Applio and its voice model have not been configured.")
    try:
        engines.resolve_model(model_id)
    except engines.EngineError as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id, directory = _new_job("applio")
    try:
        audio_path = await _save_audio(audio, directory / "source")
    except Exception:
        with job_lock:
            jobs.pop(job_id, None)
        raise
    _schedule(
        engines.convert,
        job_id,
        audio=audio_path,
        model_id=model_id,
        output=directory / "output.wav",
    )
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with job_lock:
        current = jobs.get(job_id)
        if current is None:
            raise HTTPException(404, "Unknown job (jobs reset on restart).")
        return dict(current)


@app.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str):
    with job_lock:
        current = jobs.get(job_id)
        if current is None or current["status"] != "completed":
            raise HTTPException(404, "Completed job not found.")
    output = DATA / job_id / "output.wav"
    if not output.is_file():
        raise HTTPException(404, "Audio output was not found.")
    return FileResponse(output, media_type="audio/wav", filename="mina-voice-" + job_id[:8] + ".wav")
