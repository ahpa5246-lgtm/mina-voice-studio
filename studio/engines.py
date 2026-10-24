"""Isolated adapters for separately installed model runtimes.

No engine is silently simulated. Each adapter must create a real WAV file.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 1200


class EngineError(RuntimeError):
    """Actionable runtime error from an engine."""


def _python(env_name: str) -> str:
    return os.environ.get(env_name, sys.executable).strip() or sys.executable


def _python_available(python: str) -> bool:
    if python == sys.executable:
        return True
    candidate = Path(python).expanduser()
    return candidate.is_file() if candidate.is_absolute() or "/" in python or "\\" in python else __import__("shutil").which(python) is not None


@lru_cache(maxsize=16)
def _module_installed(python: str, module: str) -> bool:
    """Check an isolated Python environment, not the server interpreter."""
    import subprocess
    try:
        found=subprocess.run(
            [python,"-c",f"import importlib.util; print(int(importlib.util.find_spec({module!r}) is not None))"],
            capture_output=True,text=True,timeout=8,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return False
    return found.returncode == 0 and found.stdout.strip() == "1"


def applio_root() -> Path | None:
    raw = os.environ.get("APPLIO_ROOT", "").strip()
    if not raw:
        return None
    root = Path(raw).expanduser().resolve()
    return root if (root / "core.py").is_file() else None


def model_catalog() -> list[dict[str, str]]:
    root = applio_root()
    if root is None:
        return []
    # Models must belong to the configured Applio installation; never accept
    # arbitrary client-provided filesystem paths.
    result = []
    logs = root / "logs"
    if not logs.is_dir():
        return result
    for path in sorted(logs.rglob("*.pth"))[:150]:
        resolved = path.resolve()
        if not resolved.is_relative_to(logs.resolve()) or not resolved.is_file():
            continue
        relative = resolved.relative_to(logs.resolve()).as_posix()
        result.append({"id": relative, "name": path.stem})
    return result


def resolve_model(model_id: str) -> tuple[Path, Path | None]:
    root = applio_root()
    if not root:
        raise EngineError("Applio is not configured. Set APPLIO_ROOT.")
    models = {m["id"] for m in model_catalog()}
    if model_id not in models:
        raise EngineError("Select an installed Applio model from the available list.")
    path = (root / "logs" / model_id).resolve()
    indices = sorted(path.parent.glob("*.index"))
    return path, (indices[0] if indices else None)


def status() -> list[dict[str, Any]]:
    chatterbox_python = _python("CHATTERBOX_PYTHON")
    # The external environment may be configured but is NOT considered verified
    # until a real generation job succeeds.
    chatterbox_configured = (
        _python_available(chatterbox_python)
        and (bool(os.getenv("CHATTERBOX_PYTHON")) or importlib.util.find_spec("chatterbox") is not None)
        and _module_installed(chatterbox_python,"chatterbox")
    )
    root = applio_root()
    models = model_catalog()
    from studio.qwen_runtime import configured as qwen_configured
    qwen_ready = qwen_configured()
    return [
        {
            "id": "qwen",
            "title": "Qwen3-TTS VoiceDesign / Base / CustomVoice",
            "operation": "speech",
            "configured": qwen_ready,
            "label": "Configured (real acoustic test required)" if qwen_ready else "Install Qwen in isolated Python environment",
            "languages": ["en","zh","ja","ko","de","fr","ru","pt","es","it"],
        },
        {
            "id": "chatterbox",
            "title": "Chatterbox Multilingual V3",
            "operation": "speech",
            "configured": chatterbox_configured,
            "label": "Configured (audio test required)" if chatterbox_configured else "Installation required",
            "languages": list("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split()),
        },
        {
            "id": "applio",
            "title": "Applio RVC",
            "operation": "conversion",
            "configured": bool(root and _python_available(_python("APPLIO_PYTHON")) and models),
            "label": "Configured (audio test required)" if root and models else "Install Applio and a voice model",
            "model_count": len(models),
        },
        {
            "id": "tts-webui",
            "title": "TTS-WebUI (local OpenAI-compatible endpoint)",
            "operation": "provider",
            "configured": __import__("studio.providers",fromlist=["local_base_url"]).local_base_url("TTS_WEBUI_URL") is not None,
            "label": "Local API URL configured; live audio test still needed",
        },
        {
            "id": "gpt-sovits",
            "title": "GPT-SoVITS (local API)",
            "operation": "provider",
            "configured": __import__("studio.providers",fromlist=["local_base_url"]).local_base_url("GPT_SOVITS_URL") is not None,
            "label": "Local API URL configured; live audio test still needed",
        },
    ]


def _execute(command: list[str], *, cwd: Path | None = None) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EngineError("The configured Python executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError("The synthesis process timed out.") from exc
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "Unknown model error")[-1600:]
        raise EngineError("Engine failed: " + detail)


def synthesize(*, text_file: Path, reference: Path | None, language: str,
               output: Path, exaggeration: float = 0.5, cfg_weight: float = 0.5,
               model: str = "multilingual-v3") -> None:
    """Use the actual upstream family in one cached, isolated stdio worker."""
    if model not in {"multilingual-v3", "turbo", "nano"}:
        raise EngineError("Unsupported Chatterbox model")
    if language not in set("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split()):
        raise EngineError("Unsupported language selection")
    if model != "multilingual-v3" and (language != "en" or not reference):
        raise EngineError("Turbo/Nano require English text and an authorized voice reference")
    from studio.chatterbox_runtime import request
    request({
        "operation": "synthesize",
        "args": {"text_file": str(text_file), "reference": str(reference) if reference else None,
                 "output": str(output), "language": language, "model_name": model,
                 "exaggeration": exaggeration, "cfg_weight": cfg_weight},
    }, python=_python("CHATTERBOX_PYTHON"))
    if not output.is_file() or output.stat().st_size < 44:
        raise EngineError("Chatterbox returned no usable WAV output")


def convert(*, audio: Path, model_id: str, output: Path,
            settings: dict | None = None) -> None:
    """Delegate to upstream Applio without mixing its dependencies with our server."""
    from studio.applio_advanced import convert_one, validate_settings
    return convert_one(audio=audio, model_id=model_id, output=output,
                       settings=settings or validate_settings())
