"""Use the actual MIT-licensed Meta Demucs CLI for two-stem separation."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from studio import engines

ROOT=Path(__file__).resolve().parents[1]
MODEL="htdemucs"
TIMEOUT=2400

def python_runtime() -> str:
    return os.getenv("DEMUCS_PYTHON","").strip() or sys.executable

def installed() -> bool:
    interpreter=python_runtime()
    return engines._python_available(interpreter) and engines._module_installed(interpreter,"demucs")

def separate(*, audio: Path, output: Path) -> None:
    """Outputs verified, uncompressed WAV stems packaged as a real ZIP."""
    if not installed():
        raise RuntimeError("Install Meta Demucs in its own environment and set DEMUCS_PYTHON")
    audio=Path(audio).resolve()
    output=Path(output).resolve()
    workdir=output.parent/"demucs-result"
    if workdir.exists():
        raise RuntimeError("Refusing to reuse an existing stem directory")
    workdir.mkdir(parents=True,exist_ok=False)
    cmd=[python_runtime(),"-m","demucs","--two-stems","vocals",
         "-n",MODEL,"-o",str(workdir),str(audio)]
    try:
        done=subprocess.run(cmd,cwd=str(ROOT),capture_output=True,text=True,
                            timeout=TIMEOUT,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Demucs failed to run: {exc}") from exc
    if done.returncode:
        raise RuntimeError("Demucs failed: "+(done.stderr or done.stdout)[-1200:])
    folder=workdir/MODEL/audio.stem
    vocal=folder/"vocals.wav"
    music=folder/"no_vocals.wav"
    from studio.app import _validate_output
    for wav in (vocal,music):
        _validate_output(wav)
    with ZipFile(output,"w",compression=ZIP_DEFLATED) as archive:
        archive.write(vocal,arcname="vocals.wav")
        archive.write(music,arcname="instrumental.wav")
    if not output.is_file() or output.stat().st_size < 100:
        raise RuntimeError("Demucs produced no stem archive")
