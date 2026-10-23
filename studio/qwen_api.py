"""Qwen3 VoiceDesign: real synthetic voice seed + persistent cast-compatible reference."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import time
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException
from studio import qwen_runtime

router=APIRouter(prefix="/api/qwen",tags=["voice-design"])


def host():
    from studio import app
    return app


@router.get("/status")
def status():
    return qwen_runtime.status()


@router.post("/design",status_code=202)
def design_voice(name:str=Form(...),description:str=Form(...),
                 seed_text:str=Form(...),language:str=Form("English"),
                 consent:bool=Form(False)):
    """Generate an actual seed, save it into the existing reference voice library."""
    if not consent:
        raise HTTPException(422,"Confirm rights to use the generated character voice")
    name=name.strip()
    description=description.strip()
    seed_text=seed_text.strip()
    allowed=set("English Chinese Japanese Korean German French Russian Portuguese Spanish Italian".split())
    if (not 1<=len(name)<=72 or not 12<=len(description)<=800
        or not 12<=len(seed_text)<=400 or language not in allowed
        or any(ord(ch)<32 for ch in name)):
        raise HTTPException(422,"Invalid character design description, text, or language")
    if not qwen_runtime.configured():
        raise HTTPException(503,"Install qwen-tts in a separate venv and set QWEN_PYTHON")
    from studio.extras import _voice_folder,_voice_list,VOICE_LIMIT
    if len(_voice_list())>=VOICE_LIMIT:
        raise HTTPException(409,"Reference voice library is full")
    app=host()
    job_id, folder=app._new_job("qwen-design")
    text_file=folder/"design-text.txt"
    text_file.write_text(seed_text,encoding="utf-8")
    def render():
        app._record(job_id,status="running")
        dest=None
        try:
            output=folder/"output.wav"
            qwen_runtime.synthesize(
                text_file=text_file,output=output,mode="design",
                language=language,instruct=description)
            from studio.extras import _voice_folder,_voice_list,VOICE_LIMIT
            if output.stat().st_size > app.MAX_UPLOAD_BYTES:
                raise RuntimeError("Designed seed exceeds the 25MB voice-reference limit")
            if len(_voice_list())>=VOICE_LIMIT:
                raise RuntimeError("Voice library is full after rendering")
            identifier=uuid4().hex
            dest=_voice_folder()/identifier
            dest.mkdir(exist_ok=False)
            shutil.copyfile(output,dest/"reference.wav")
            record={"id":identifier,"name":name,"filename":"reference.wav",
                    "created":int(time.time()),"origin":"qwen-design",
                    "seed_text":seed_text,"language":language,
                    "description":description}
            (dest/"voice.json").write_text(
                json.dumps(record,ensure_ascii=False),encoding="utf-8")
        except Exception as exc:
            if dest is not None:shutil.rmtree(dest,ignore_errors=True)
            app._record(job_id,status="failed",error=str(exc)[:800])
        else:
            app._record(job_id,status="completed",
                        download=f"/api/jobs/{job_id}/audio",
                        voice=record)
    try:
        app.pool.submit(render)
    except RuntimeError as exc:
        app._discard_job(job_id)
        raise HTTPException(503,"Synthesis queue unavailable") from exc
    return {"id":job_id,"status":"queued"}
