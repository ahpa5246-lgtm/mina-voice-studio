"""Persistent stdio-only Chatterbox model host.

One private worker per Mina server keeps weights warm across synthesis requests.
No TCP listener. Worker restarts after failure/timeout; caller gets a real error.
"""
from __future__ import annotations
import atexit
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import RLock, Thread

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/"scripts"/"chatterbox_worker.py"
TIMEOUT=1200
_lock=RLock()
_process=None
_python=None
_responses=None
_log_handle=None

def status() -> dict:
    with _lock:
        running=_process is not None and _process.poll() is None
        return {"worker_running":running,"pid":_process.pid if running else None,
                "mode":"single cached upstream model / isolated stdio",
                "model_audio_tested":False}

def release():
    global _process,_python,_responses,_log_handle
    with _lock:
        if _process is not None and _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
                _process.wait(timeout=5)
        _process=None
        _python=None
        _responses=None
        if _log_handle is not None:
            _log_handle.close()
        _log_handle=None

atexit.register(release)

def _launch(python: str):
    global _process,_python,_responses,_log_handle
    directory=Path(os.getenv("MINA_DATA_DIR",str(ROOT/"data")))/"_logs"
    directory.mkdir(parents=True,exist_ok=True)
    logfile=directory/"chatterbox-worker.log"
    if logfile.exists() and logfile.stat().st_size>1024*1024:
        logfile.replace(directory/"chatterbox-worker.old.log")
    _log_handle=logfile.open("a",encoding="utf-8")
    _process=subprocess.Popen(
        [python,str(WORKER),"--serve-stdio"],
        cwd=str(ROOT),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=_log_handle,text=True,encoding="utf-8",bufsize=1)
    _python=python
    _responses=Queue()
    launched_process=_process
    launched_queue=_responses
    def read():
        try:
            for line in launched_process.stdout:
                launched_queue.put(line)
        finally:
            launched_queue.put(None)
    Thread(target=read,daemon=True,name="mina-chatterbox-stdout").start()

def request(payload: dict, *, python: str | None = None, timeout: float = TIMEOUT) -> dict:
    if not isinstance(payload,dict) or payload.get("operation") not in {"ping","synthesize"}:
        raise ValueError("Unsupported worker operation")
    python=python or os.getenv("CHATTERBOX_PYTHON") or sys.executable
    with _lock:
        if (_process is None or _process.poll() is not None or _python!=python):
            release()
            _launch(python)
        try:
            _process.stdin.write(json.dumps(payload,ensure_ascii=False)+"\n")
            _process.stdin.flush()
            response=_responses.get(timeout=timeout)
            if response is None:
                raise RuntimeError("Chatterbox worker exited unexpectedly")
            reply=json.loads(response)
            if not reply.get("ok"):
                raise RuntimeError(str(reply.get("error","Unknown Chatterbox error"))[:800])
            return reply
        except (OSError,BrokenPipeError,Empty,json.JSONDecodeError,RuntimeError) as exc:
            release()
            raise RuntimeError("Chatterbox worker failed: "+str(exc)) from exc
