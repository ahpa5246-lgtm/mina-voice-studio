"""A single bounded private Qwen3-TTS stdio worker; no public inference server."""
import atexit
import json
import os
from pathlib import Path
from queue import Queue, Empty
import subprocess
from threading import RLock, Thread

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/"scripts"/"qwen_worker.py"
_lock=RLock()
_process=None
_responses=None
_python=None
_log=None
MAX_REQUEST_SECONDS=1200

def interpreter():
    return os.getenv("QWEN_PYTHON","").strip()

def configured():
    py=interpreter()
    if not py:
        return False
    from studio.engines import _python_available, _module_installed
    return _python_available(py) and _module_installed(py,"qwen_tts")

def status():
    with _lock:
        alive=_process is not None and _process.poll() is None
        return {"configured":configured(),"process_running":alive,
                "model_weight_inference_verified":False,
                "supported_languages":"English Chinese Japanese Korean German French Russian Portuguese Spanish Italian".split()}

def release():
    global _process,_responses,_python,_log
    with _lock:
        p=_process
        _process=None
        _responses=None
        _python=None
        if p is not None and p.poll() is None:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill();p.wait(timeout=5)
        if _log is not None:_log.close()
        _log=None

atexit.register(release)

def _start(py):
    global _process,_responses,_python,_log
    logs=Path(os.getenv("MINA_DATA_DIR",str(ROOT/"data")))/"_logs"
    logs.mkdir(parents=True,exist_ok=True)
    _log=(logs/"qwen3-tts.log").open("a",encoding="utf-8")
    process=subprocess.Popen(
        [py,str(WORKER),"--serve-stdio"],
        cwd=str(ROOT),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=_log,text=True,encoding="utf-8",bufsize=1)
    _process=process
    _python=py
    responses=Queue()
    _responses=responses
    def drain():
        try:
            for line in process.stdout:
                responses.put(line)
        finally:responses.put(None)
    Thread(target=drain,name="qwen-stdout",daemon=True).start()

def request(spec,timeout=MAX_REQUEST_SECONDS):
    if not isinstance(spec,dict):
        raise ValueError("Invalid Qwen request")
    py=interpreter()
    if not py:
        raise RuntimeError("QWEN_PYTHON is not configured")
    with _lock:
        if _process is None or _process.poll() is not None or _python!=py:
            release()
            _start(py)
        try:
            _process.stdin.write(json.dumps(spec,ensure_ascii=False)+"\n")
            _process.stdin.flush()
            line=_responses.get(timeout=timeout)
            if line is None:
                raise RuntimeError("Qwen worker exited unexpectedly")
            result=json.loads(line)
            if not isinstance(result,dict) or not result.get("ok"):
                raise RuntimeError(str(result.get("error","Invalid model result"))[:800])
            return result
        except (OSError,Empty,ValueError,RuntimeError) as exc:
            release()
            raise RuntimeError("Qwen worker failed: "+str(exc)) from exc

def synthesize(*,text_file:Path,output:Path,mode:str,language:str="English",
               instruct:str="",speaker:str="Ryan",ref_audio:Path|None=None,
               ref_text:str=""):
    from studio.app import _validate_output
    spec={"mode":mode,"text":text_file.read_text(encoding="utf-8"),
          "output":str(output),"language":language,
          "instruct":instruct,"speaker":speaker,
          "ref_audio":str(ref_audio) if ref_audio else "","ref_text":ref_text}
    request(spec)
    _validate_output(output)
