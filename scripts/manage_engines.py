"""Explicit isolated installers for original upstream voice engines.

Run: py -3.12 scripts/manage_engines.py install qwen
Run: py -3.11 scripts/manage_engines.py install chatterbox
Run: python scripts/manage_engines.py status

Never downloads checkpoints unless explicitly requested (or first inference).
Applio must be installed using its official instructions plus an RVC model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / ".venvs"
SPECS = {
    "qwen": {"package": "qwen-tts", "module": "qwen_tts", "python": (3, 12),
             "env_var": "QWEN_PYTHON"},
    "chatterbox": {"package": "chatterbox-tts", "module": "chatterbox",
                   "python": (3, 11), "env_var": "CHATTERBOX_PYTHON"},
    "whisper": {"package": "faster-whisper", "module": "faster_whisper",
                "python": (3, 11), "env_var": "WHISPER_PYTHON"},
    "demucs": {"package": "demucs", "module": "demucs",
               "python": (3, 11), "env_var": "DEMUCS_PYTHON"},
}
QWEN_WEIGHTS = {
    "voice-design": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "base": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "custom": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
}


def venv_python(engine: str) -> Path:
    home = ENV_DIR / engine
    return home / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def probe(interpreter: str, module: str) -> dict:
    script = (
        "import importlib.util,json,platform,sys;"
        "print(json.dumps({'python':platform.python_version(),"
        "'module_available':importlib.util.find_spec(%r) is not None}))" % module
    )
    try:
        process = subprocess.run([interpreter, "-c", script], text=True,
                                 capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"module_available": False, "reason": type(exc).__name__}
    if process.returncode:
        return {"module_available": False, "reason": "interpreter probe failed"}
    try:
        return json.loads(process.stdout)
    except ValueError:
        return {"module_available": False, "reason": "malformed interpreter probe"}


def status() -> dict:
    entries = []
    for key, spec in SPECS.items():
        python = os.environ.get(spec["env_var"], "").strip() or str(venv_python(key))
        ready = probe(python, spec["module"])
        entries.append({
            "engine": key, "environment": spec["env_var"],
            "module_installed": bool(ready.get("module_available")),
            "python_version": ready.get("python"),
            "gpu_audio_test_passed": False,
        })
    from studio import engines
    model_count = len(engines.model_catalog())
    entries.append({"engine": "applio", "environment": "APPLIO_ROOT / APPLIO_PYTHON",
                    "module_installed": bool(engines.applio_root() and model_count),
                    "installed_rvc_models": model_count, "gpu_audio_test_passed": False,
                    "note": "Official Applio installation and separate model .pth required."})
    return {"engines": entries,
            "note": "Module checks neither load checkpoints nor execute GPU inference."}


def install(engine: str, *, python: str | None = None,
            download_weights: bool = False, checkpoint: str = "voice-design") -> Path:
    if engine not in SPECS:
        raise ValueError("Unknown engine. Install Applio from its original repository.")
    spec = SPECS[engine]
    if download_weights and engine != "qwen":
        raise ValueError("Checkpoint pre-download is supported only for Qwen.")
    interpreter = python or sys.executable
    result = subprocess.run([interpreter, "-c",
                            "import sys;print('%s.%s'%(sys.version_info.major,sys.version_info.minor))"],
                            capture_output=True, text=True, timeout=30, check=True)
    expected = ".".join(map(str, spec["python"]))
    if result.stdout.strip() != expected:
        raise RuntimeError(f"{engine} requires Python {expected} for this installer; "
                           f"received {result.stdout.strip()}. Run through the expected interpreter.")
    path = venv_python(engine)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([interpreter, "-m", "venv", str(ENV_DIR / engine)], check=True)
    subprocess.run([str(path), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(path), "-m", "pip", "install", spec["package"]], check=True)
    if not probe(str(path), spec["module"]).get("module_available"):
        raise RuntimeError("Installation did not produce an importable engine.")
    if download_weights:
        if checkpoint not in QWEN_WEIGHTS:
            raise ValueError("Unknown official Qwen checkpoint")
        subprocess.run([str(path), "-m", "pip", "install", "huggingface_hub"], check=True)
        script = "from huggingface_hub import snapshot_download; snapshot_download(%r)" % QWEN_WEIGHTS[checkpoint]
        subprocess.run([str(path), "-c", script], check=True)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    installer = commands.add_parser("install")
    installer.add_argument("engine", choices=sorted(SPECS))
    installer.add_argument("--python", help="Full base Python interpreter path")
    installer.add_argument("--download-weights", action="store_true",
                           help="Explicit multi-GB Qwen checkpoint download")
    installer.add_argument("--checkpoint", choices=sorted(QWEN_WEIGHTS), default="voice-design")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
        return 0
    path = install(args.engine, python=args.python,
                   download_weights=args.download_weights, checkpoint=args.checkpoint)
    env = SPECS[args.engine]["env_var"]
    print(json.dumps({"engine": args.engine, "python": str(path),
                      "powershell": f'$env:{env} = "{path}"',
                      "bash": f'export {env}="{path}"',
                      "model_inference_verified": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
