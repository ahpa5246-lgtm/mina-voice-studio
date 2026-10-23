"""Actual local audio tools routes. No synthetic output or fake model inference."""
from __future__ import annotations

from concurrent.futures import Future
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from studio import audio_tools, engines, providers, training, separation
from studio.text import normalize_text, MAX_DOCUMENT_CHARS

router = APIRouter(prefix="/api")
VOICE_LIMIT = 24
NAME_LIMIT = 72
VOICE_ID = re.compile(r"^[0-9a-f]{32}$")


def _app():
    from studio import app as server
    return server


def _voice_folder() -> Path:
    directory = _app().DATA / "_voices"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _metadata(directory: Path) -> dict | None:
    record = directory / "voice.json"
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        if data.get("id") != directory.name or not VOICE_ID.fullmatch(directory.name):
            return None
        audio = directory / data.get("filename", "")
        if not audio.is_file() or audio.parent != directory:
            return None
        return {"id": data["id"], "name": data["name"],
                "created": data["created"], "filename": data["filename"]}
    except (OSError, KeyError, ValueError, TypeError):
        return None


def _voice_list() -> list[dict]:
    return sorted([item for folder in _voice_folder().iterdir() if folder.is_dir()
                   if (item := _metadata(folder))],
                  key=lambda item: item["created"], reverse=True)


def _voice_file(voice_id: str) -> Path:
    if not VOICE_ID.fullmatch(voice_id):
        raise HTTPException(404, "Voice not found")
    folder = _voice_folder() / voice_id
    record = _metadata(folder)
    if not record:
        raise HTTPException(404, "Voice not found")
    return folder / record["filename"]


def _stt_python() -> str | None:
    raw = os.getenv("WHISPER_PYTHON", "").strip()
    if not raw:
        return None
    return raw if engines._python_available(raw) else None


@router.get("/tools")
def tool_status():
    return {"tools": [
        {"id": "separate", "label": "Demucs vocals / instrumental stems",
         "ready": separation.installed(),
         "detail": "Meta Demucs two-stem CLI; weights downloaded on first use"},
        {"id": "enhance", "label": "WAV cleanup / peak normalization",
         "ready": True, "detail": "Pure Python PCM-16, no neural denoising"},
        {"id": "quality", "label": "Technical WAV diagnostics",
         "ready": True, "detail": "PCM-16 only"},
        {"id": "voice-library", "label": "Private local reference library",
         "ready": True, "detail": f"{len(_voice_list())}/{VOICE_LIMIT} voices saved"},
        {"id": "transcribe", "label": "Faster Whisper transcription",
         "ready": _stt_python() is not None,
         "detail": "Requires WHISPER_PYTHON and installed faster-whisper; audio test pending"},
        {"id": "manual-dub", "label": "Scripted voiceover / manual dubbing",
         "ready": any(e["id"] == "chatterbox" and e["configured"] for e in engines.status()),
         "detail": "User supplies translated script, not automatic translation/synchronization"},
        {"id": "mic", "label": "Microphone clip capture",
         "ready": True, "detail": "Browser audio input; not low-latency live voice conversion"},
        {"id": "training", "label": "Applio RVC training CLI",
         "ready": training.status()["ready"],
         "detail": training.status()["reason"] + "; GPU training has not been benchmarked"},
        {"id": "realtime", "label": "Streaming realtime voice changer",
         "ready": False, "detail": "No low-latency GPU streaming bridge implemented"},
    ] + providers.available()}


@router.get("/voices")
def list_voices():
    return {"voices": _voice_list(), "limit": VOICE_LIMIT}


@router.post("/voices", status_code=201)
async def add_voice(name: str = Form(...), consent: bool = Form(False),
                    audio: UploadFile = File(...)):
    if not consent:
        raise HTTPException(422, "Explicit permission to store this voice is required.")
    name = name.strip()
    if not name or len(name) > NAME_LIMIT or any(ord(c) < 32 for c in name):
        raise HTTPException(422, "Voice name must contain 1-72 printable characters.")
    if len(_voice_list()) >= VOICE_LIMIT:
        raise HTTPException(409, "Voice library is full; delete an unused voice first.")
    identifier = uuid4().hex
    destination = _voice_folder() / identifier
    destination.mkdir(parents=False, exist_ok=False)
    try:
        source = await _app()._save_audio(audio, destination / "reference")
        import time
        record = {"id": identifier, "name": name,
                  "filename": source.name, "created": int(time.time())}
        (destination / "voice.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return {"voice": record}


@router.delete("/voices/{voice_id}")
def delete_voice(voice_id: str):
    source = _voice_file(voice_id)
    shutil.rmtree(source.parent)
    return {"deleted": True, "id": voice_id}


@router.get("/voices/{voice_id}/audio")
def voice_audio(voice_id: str):
    path = _voice_file(voice_id)
    media = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac",
             ".ogg": "audio/ogg", ".m4a": "audio/mp4"}[path.suffix]
    return FileResponse(path, media_type=media, filename=path.name)


@router.post("/enhance", status_code=202)
async def enhance(
    audio: UploadFile = File(...),
    highpass_hz: float = Form(65), peak_dbfs: float = Form(-1),
    noise_gate: bool = Form(False),
):
    if Path(audio.filename or "").suffix.lower() != ".wav":
        raise HTTPException(422, "Cleanup requires PCM-16 WAV input.")
    if not 0 <= highpass_hz <= 200 or not -18 <= peak_dbfs <= -0.5:
        raise HTTPException(422, "Invalid enhancement settings.")
    server = _app()
    job, directory = server._new_job("enhance")
    try:
        source = await server._save_audio(audio, directory / "source")
    except Exception:
        server._discard_job(job)
        raise
    server._schedule(audio_tools.enhance_wav, job,
                     audio=source, output=directory / "output.wav",
                     highpass_hz=highpass_hz, peak_dbfs=peak_dbfs,
                     noise_gate=noise_gate)
    return {"id": job, "status": "queued"}


@router.post("/analyze")
async def analyze(audio: UploadFile = File(...)):
    if Path(audio.filename or "").suffix.lower() != ".wav":
        raise HTTPException(422, "Quality analyzer requires PCM-16 WAV.")
    from scripts.quality_report import analyze_wav
    with tempfile.TemporaryDirectory(dir=_app().DATA) as temporary:
        source = await _app()._save_audio(audio, Path(temporary) / "sample")
        try:
            return analyze_wav(source)
        except (ValueError, OSError, EOFError) as exc:
            raise HTTPException(422, str(exc)) from exc


def _transcribe_task(job: str, source: Path, language: str, model: str) -> None:
    server = _app()
    server._record(job, status="running")
    target = source.parent / "transcription.json"
    command = [
        _stt_python() or sys.executable,
        str(server.ROOT / "scripts" / "whisper_worker.py"),
        "--audio", str(source), "--output", str(target),
        "--language", language, "--model", model,
    ]
    try:
        engines._execute(command)
        result = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(result.get("text"), str):
            raise ValueError("Whisper did not produce a text transcript.")
    except Exception as exc:
        server._record(job, status="failed", error=str(exc)[:800])
    else:
        server._record(job, status="completed", transcript=result)


@router.post("/transcribe", status_code=202)
async def transcribe(audio: UploadFile = File(...),
                     language: str = Form("auto"), model: str = Form("small")):
    if not _stt_python():
        raise HTTPException(503, "Install faster-whisper and set WHISPER_PYTHON.")
    if language not in {"auto", "ar", "en"} or model not in {"tiny", "base", "small", "medium", "large-v3"}:
        raise HTTPException(422, "Unsupported transcription settings.")
    server = _app()
    job, directory = server._new_job("transcribe")
    try:
        source = await server._save_audio(audio, directory / "source")
    except Exception:
        server._discard_job(job)
        raise
    try:
        server.pool.submit(_transcribe_task, job, source, language, model)
    except RuntimeError as exc:
        server._discard_job(job)
        raise HTTPException(503, "Job queue is unavailable.") from exc
    return {"id": job, "status": "queued"}


@router.post("/voiceover", status_code=202)
async def voiceover(
    text: str = Form(...), language: str = Form("ar"),
    voice_id: str = Form(""), consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "Confirm you have permission to use this voice.")
    server = _app()
    text = normalize_text(text)
    if not 1 <= len(text) <= MAX_DOCUMENT_CHARS or language not in server.LANGUAGES:
        raise HTTPException(422, "Unsupported language or invalid text length.")
    if not server._configured("chatterbox"):
        raise HTTPException(503, "Chatterbox V3 is not installed/configured.")
    reference = _voice_file(voice_id) if voice_id else None
    job, directory = server._new_job("manual-dub")
    (directory / "text.txt").write_text(text, encoding="utf-8")
    server._schedule(engines.synthesize, job,
                     text_file=directory / "text.txt", language=language,
                     reference=reference, output=directory / "output.wav")
    return {"id": job, "status": "queued"}


@router.post("/provider/speech", status_code=202)
async def provider_speech(
    text: str = Form(...), provider: str = Form(...),
    language: str = Form("en"), voice_id: str = Form(""),
    prompt_text: str = Form(""), voice: str = Form("default"),
    model: str = Form("tts-1"), consent: bool = Form(False),
):
    if not consent:
        raise HTTPException(422, "Confirm you have permission to use this voice.")
    text = normalize_text(text)
    if not 1 <= len(text) <= MAX_DOCUMENT_CHARS or provider not in {"gpt-sovits", "tts-webui"}:
        raise HTTPException(422, "Invalid provider request.")
    variable = "GPT_SOVITS_URL" if provider == "gpt-sovits" else "TTS_WEBUI_URL"
    if not providers.local_base_url(variable):
        raise HTTPException(503, "Provider is not configured on a loopback endpoint.")
    if language not in {"en", "zh", "ja", "ko"}:
        raise HTTPException(422, "Language is not supported by this connector.")
    reference = _voice_file(voice_id) if voice_id else None
    if provider == "gpt-sovits" and (reference is None or not prompt_text.strip()):
        raise HTTPException(422, "GPT-SoVITS needs an installed voice and its source transcript.")
    if len(prompt_text) > 800 or len(voice) > 100 or len(model) > 100:
        raise HTTPException(422, "Provider configuration exceeds maximum length.")
    server = _app()
    job, directory = server._new_job(provider)
    server._schedule(providers.synthesize_provider, job,
                     provider=provider, text=text, language=language,
                     reference=reference, prompt_text=prompt_text,
                     voice=voice, model=model, output=directory / "output.wav")
    return {"id": job, "status": "queued"}


def _train_task(job: str, directory: Path, name: str,
                epochs: int, batch: int, sample_rate: int, gpu: int) -> None:
    """Run upstream Applio CLI in the already bounded single-worker queue."""
    server = _app()
    server._record(job, status="running", stage="preflight")
    try:
        result = training.run_training(
            model_name=name, epochs=epochs, batch_size=batch,
            sample_rate=sample_rate, gpu_index=gpu,
            log=directory / "training.log",
            on_stage=lambda stage: server._record(job, stage=stage)
        )
    except Exception as exc:
        server._record(job, status="failed", error=str(exc)[:800])
    else:
        server._record(job, status="completed", training=result)


@router.get("/training/status")
def training_status():
    return training.status()


@router.post("/train", status_code=202)
def launch_training(
    model_name: str = Form(...), epochs: int = Form(40),
    batch_size: int = Form(4), sample_rate: int = Form(40000),
    gpu: int = Form(0), consent: bool = Form(False),
    acknowledge: bool = Form(False),
):
    if not consent or not acknowledge:
        raise HTTPException(422, "Speaker permission and long-running GPU training acknowledgement required.")
    if not training.MODEL_NAME.fullmatch(model_name):
        raise HTTPException(422, "Invalid model name.")
    if not (10 <= epochs <= 2000 and 1 <= batch_size <= 16 and
            sample_rate in {32000, 40000, 48000} and 0 <= gpu <= 7):
        raise HTTPException(422, "Invalid training hyperparameters.")
    readiness = training.status()
    if not readiness["ready"]:
        raise HTTPException(503, readiness["reason"])
    root = engines.applio_root()
    if (root / "logs" / model_name).exists():
        raise HTTPException(409, "Model already exists; refusing to overwrite.")
    server = _app()
    job, directory = server._new_job("applio-training")
    server.pool.submit(_train_task, job, directory, model_name,
                       epochs, batch_size, sample_rate, gpu)
    return {"id": job, "status": "queued", "note": "Training requested, not yet completed."}


@router.get("/jobs/{job_id}/training-log")
def training_log(job_id: str):
    server = _app()
    with server.job_lock:
        job = server.jobs.get(job_id)
        if job is None or job.get("engine") != "applio-training":
            raise HTTPException(404, "Training job not found")
    path = server.DATA / job_id / "training.log"
    if not path.is_file():
        raise HTTPException(404, "Training log not yet available")
    return FileResponse(path, media_type="text/plain", filename="applio-training.log")

@router.get("/transcriptions/{job_id}/{format}")
def download_subtitles(job_id: str, format: str):
    """Export actual Whisper segments as UTF-8 captions, no fake timestamps."""
    from studio.subtitles import subtitle_text
    from studio import app as server
    if format not in {"srt","vtt"}:
        raise HTTPException(404,"Supported formats: srt, vtt")
    with server.job_lock:
        job = server.jobs.get(job_id)
        if not job or job.get("engine") != "transcribe" or job.get("status") != "completed":
            raise HTTPException(404,"Completed transcription not found")
        result = job.get("transcript")
        if not isinstance(result,dict):
            raise HTTPException(404,"No transcript for this job")
    try:
        output = subtitle_text(result.get("segments",[]),format)
    except (ValueError,TypeError,KeyError) as exc:
        raise HTTPException(422,"Transcription has invalid timestamps") from exc
    return Response(
        output,media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition":f'attachment; filename="mina-transcript-{job_id[:8]}.{format}"',
                 "Cache-Control":"no-store"},
    )

@router.post("/separate", status_code=202)
async def separate_stems(audio: UploadFile = File(...), consent: bool = Form(False)):
    """Launch real upstream Demucs without synthesizing fake separation output."""
    if not consent:
        raise HTTPException(422,"Confirm permission to process this recording.")
    if not separation.installed():
        raise HTTPException(503,"Demucs not installed. Install into DEMUCS_PYTHON environment.")
    host=_app()
    job_id, directory=host._new_job("demucs-separation")
    try:
        source=await host._save_audio(audio,directory/"source")
    except Exception:
        host._discard_job(job_id)
        raise
    def work():
        host._record(job_id,status="running")
        try:
            destination=directory/"stems.zip"
            separation.separate(audio=source,output=destination)
        except Exception as exc:
            host._record(job_id,status="failed",error=str(exc)[:800])
        else:
            host._record(job_id,status="completed",
                         download=f"/api/separation/{job_id}/archive")
    try:
        host.pool.submit(work)
    except RuntimeError as exc:
        host._discard_job(job_id)
        raise HTTPException(503,"Processing queue unavailable.") from exc
    return {"id":job_id,"status":"queued"}


@router.get("/separation/{job_id}/archive")
def download_stems(job_id: str):
    host=_app()
    with host.job_lock:
        job=host.jobs.get(job_id)
        if not job or job.get("engine")!="demucs-separation" or job.get("status")!="completed":
            raise HTTPException(404,"Separated stems not available")
    destination=host.DATA/job_id/"stems.zip"
    if not destination.is_file():
        raise HTTPException(404,"Stem archive missing")
    return FileResponse(destination,media_type="application/zip",
                        filename="mina-demucs-stems.zip")
