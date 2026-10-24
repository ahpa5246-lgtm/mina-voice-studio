"""Local-first FastAPI server with bounded GPU work and secure audio ingestion.

Not a public multi-user service: no login, private per-user storage, or remote auth.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4
import wave

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from studio import engines
from studio.text import MAX_DOCUMENT_CHARS, normalize_text

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv("MINA_DATA_DIR", str(ROOT / "data"))).expanduser().resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ACTIVE_JOBS = 5
MAX_CACHED_JOBS = 64
JOB_TTL_SECONDS = 24 * 60 * 60
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
LANGUAGES = set("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split())

app = FastAPI(title="Mina Voice Studio", version="0.2.0", docs_url="/api/docs", redoc_url=None)
allowed_hosts = [item.strip() for item in os.getenv(
    "MINA_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,[::1]"
).split(",") if item.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.mount("/assets", StaticFiles(directory=str(ROOT / "studio" / "static")), name="assets")
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mina-audio")
jobs: dict[str, dict] = {}
job_lock = threading.RLock()
RUNNING = {"queued", "running"}


@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    """Block cross-origin form posts to loopback; host allowlist blocks rebinding."""
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            current_host = request.headers.get("host", "").lower()
            # Explicit matching port is important for localhost origin checks.
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != current_host:
                return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _cleanup_expired_locked() -> None:
    now = time.time()
    removable = [
        key for key, data in jobs.items()
        if data["status"] not in RUNNING and now - data["updated"] > JOB_TTL_SECONDS
    ]
    completed = sorted(
        (k for k, v in jobs.items() if v["status"] not in RUNNING and k not in removable),
        key=lambda key: jobs[key]["updated"]
    )
    overflow = max(0, len(jobs) - len(removable) - MAX_CACHED_JOBS)
    removable.extend(completed[:overflow])
    for job_id in removable:
        jobs.pop(job_id, None)
        shutil.rmtree(DATA / job_id, ignore_errors=True)
    # Reclaim stale job directories left from earlier server lifetimes.
    for directory in DATA.iterdir():
        if directory.name in jobs or directory.name.startswith("_") or not directory.is_dir():
            continue
        try:
            age = now - directory.stat().st_mtime
        except OSError:
            continue
        if age > JOB_TTL_SECONDS:
            shutil.rmtree(directory, ignore_errors=True)


def _record(job_id: str, **changes) -> None:
    with job_lock:
        if job_id in jobs:
            jobs[job_id].update(changes, updated=time.time())


def _schedule(operation, job_id: str, **kwargs) -> None:
    def work():
        _record(job_id, status="running")
        try:
            operation(**kwargs)
            _validate_output(kwargs["output"])
        except Exception as exc:
            _record(job_id, status="failed", error=str(exc)[:800])
        else:
            _record(job_id, status="completed", download=f"/api/jobs/{job_id}/audio")
    try:
        pool.submit(work)
    except RuntimeError as exc:
        _record(job_id, status="failed", error="The processing queue is unavailable.")
        raise HTTPException(503, "Processing queue is unavailable.") from exc


def _new_job(engine: str) -> tuple[str, Path]:
    with job_lock:
        _cleanup_expired_locked()
        if sum(data["status"] in RUNNING for data in jobs.values()) >= MAX_ACTIVE_JOBS:
            raise HTTPException(429, "Audio queue is full. Try again when a job completes.")
        job_id = uuid4().hex
        directory = DATA / job_id
        directory.mkdir(parents=True, exist_ok=False)
        now = time.time()
        jobs[job_id] = {
            "id": job_id, "engine": engine, "status": "queued",
            "created": int(now), "updated": now, "download": None, "error": None
        }
        return job_id, directory


def _discard_job(job_id: str) -> None:
    with job_lock:
        jobs.pop(job_id, None)
    shutil.rmtree(DATA / job_id, ignore_errors=True)


def _valid_signature(suffix: str, header: bytes) -> bool:
    signatures = {
        ".wav": len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE",
        ".flac": header.startswith(b"fLaC"),
        ".ogg": header.startswith(b"OggS"),
        ".m4a": len(header) >= 8 and header[4:8] == b"ftyp",
        ".mp3": header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 255 and (header[1] & 0xE0) == 0xE0
        ),
    }
    return signatures.get(suffix, False)


async def _save_audio(upload: UploadFile, destination: Path) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(422, "Accepted: WAV, MP3, FLAC, OGG and M4A.")
    path = destination.with_suffix(suffix)
    amount = 0
    try:
        with path.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                amount += len(chunk)
                if amount > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Audio file exceeds the 25 MB limit.")
                stream.write(chunk)
        with path.open("rb") as source:
            header = source.read(32)
        if amount < 44 or not _valid_signature(suffix, header):
            raise HTTPException(422, "Unrecognized or empty audio file.")
        if suffix == ".wav":
            try:
                with wave.open(str(path), "rb") as decoded:
                    if decoded.getnframes() < 1 or not (8000 <= decoded.getframerate() <= 192000):
                        raise ValueError("Invalid WAV frame count or sample rate")
            except (wave.Error, ValueError, EOFError) as exc:
                raise HTTPException(422, "Invalid WAV audio.") from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return path


def _validate_output(output: Path) -> None:
    if not output.is_file():
        raise ValueError("Engine did not produce the requested WAV file.")
    try:
        with wave.open(str(output), "rb") as decoded:
            if decoded.getnframes() < 1 or decoded.getnchannels() not in (1, 2):
                raise ValueError("Engine returned empty/invalid audio.")
            if not 8000 <= decoded.getframerate() <= 192000:
                raise ValueError("Invalid output sample rate.")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Engine returned invalid WAV data.") from exc


def _configured(engine_id: str) -> bool:
    return any(e["id"] == engine_id and e["configured"] for e in engines.status())


@app.get("/")
def home():
    return FileResponse(ROOT / "studio" / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"version": app.version, "local_only_default": True, "engines": engines.status()}


@app.get("/api/verification/status")
def acoustic_verification_status():
    from studio.verification import status
    return status(DATA)


@app.get("/api/models")
def models():
    return {"applio": engines.model_catalog()}


@app.post("/api/speech", status_code=202)
async def make_speech(
    text: str = Form(...),
    language: str = Form("ar"),
    model: str = Form("multilingual-v3"),
    consent: bool = Form(False),
    reference: UploadFile | None = File(None),
    exaggeration: float = Form(0.5),
    cfg_weight: float = Form(0.5),
):
    if not consent:
        raise HTTPException(422, "Confirm that you have permission to use this voice.")
    text = normalize_text(text)
    if not 1 <= len(text) <= MAX_DOCUMENT_CHARS:
        raise HTTPException(422, f"Text must contain 1-{MAX_DOCUMENT_CHARS} characters.")
    if language not in LANGUAGES:
        raise HTTPException(422, "Unsupported language.")
    if not 0.25 <= exaggeration <= 1.0 or not 0 <= cfg_weight <= 1.0:
        raise HTTPException(422, "Invalid voice settings.")
    if model not in {"multilingual-v3", "turbo", "nano"}:
        raise HTTPException(422, "Unknown Chatterbox model.")
    if model != "multilingual-v3" and (language != "en" or reference is None):
        raise HTTPException(422, "Turbo and Nano require English and an authorized voice reference.")
    if not _configured("chatterbox"):
        raise HTTPException(503, "Chatterbox has not been installed/configured.")
    job_id, directory = _new_job("chatterbox")
    try:
        text_file = directory / "text.txt"
        text_file.write_text(text, encoding="utf-8")
        reference_path = await _save_audio(reference, directory / "reference") if reference else None
    except Exception:
        _discard_job(job_id)
        raise
    _schedule(engines.synthesize, job_id,
              text_file=text_file, reference=reference_path, language=language,
              output=directory / "output.wav", exaggeration=exaggeration, cfg_weight=cfg_weight,
              model=model)
    return {"id": job_id, "status": "queued"}


@app.post("/api/convert", status_code=202)
async def make_conversion(
    audio: UploadFile = File(...),
    model_id: str = Form(...),
    consent: bool = Form(False),
    pitch: int = Form(0),
    index_rate: float = Form(0.3),
    protect: float = Form(0.33),
    f0_method: str = Form("rmvpe"),
    autotune: bool = Form(False),
    cleanup: str = Form("off"),
    cleanup_strength: float = Form(12.0),
):
    if not consent:
        raise HTTPException(422, "Confirm permission to use this voice.")
    if not _configured("applio"):
        raise HTTPException(503, "Applio and an RVC voice model must be configured.")
    from studio.applio_advanced import validate_settings
    try:
        engines.resolve_model(model_id)
        settings = validate_settings(
            pitch=pitch, index_rate=index_rate, protect=protect,
            f0_method=f0_method, autotune=autotune,
            cleanup=cleanup, cleanup_strength=cleanup_strength,
        )
    except (engines.EngineError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    job_id, directory = _new_job("applio")
    try:
        audio_path = await _save_audio(audio, directory / "source")
    except Exception:
        _discard_job(job_id)
        raise
    _schedule(engines.convert, job_id, audio=audio_path,
              model_id=model_id, output=directory / "output.wav",
              settings=settings)
    return {"id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with job_lock:
        current = jobs.get(job_id)
        if current is None:
            raise HTTPException(404, "Unknown job.")
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
    return FileResponse(output, media_type="audio/wav", filename=f"mina-voice-{job_id[:8]}.wav")

# Extra audio workspaces share the same bounded queue and safety middleware.
from studio.extras import router as extra_router
app.include_router(extra_router)

from studio.applio_api import router as applio_router
app.include_router(applio_router)

@app.get("/api/runtime/chatterbox")
def chatterbox_process_status():
    from studio.chatterbox_runtime import status
    return status()


@app.post("/api/runtime/chatterbox/unload")
def unload_chatterbox():
    from studio.chatterbox_runtime import release
    with job_lock:
        if any(j["engine"] in {"chatterbox","manual-dub"} and j["status"] in RUNNING for j in jobs.values()):
            raise HTTPException(409,"A Chatterbox job is active; cannot unload its weights.")
        release()
    return {"unloaded": True}


# Consent-aware cartoon cast, multi-speaker dialogue and episode exports.
from studio.cast_api import router as cast_router
app.include_router(cast_router)

from studio.qwen_api import router as qwen_router
app.include_router(qwen_router)
