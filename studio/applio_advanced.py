"""Applio advanced CLI adapters in a dedicated installed Applio environment."""
from __future__ import annotations
import os
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from studio import engines

ROOT = Path(__file__).resolve().parents[1]
NEW_MODEL = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,39}$")


def validate_settings(*, pitch: int = 0, index_rate: float = 0.3,
                      protect: float = 0.33, f0_method: str = "rmvpe",
                      autotune: bool = False, cleanup: str = "off",
                      cleanup_strength: float = 12) -> dict:
    if not (-24 <= pitch <= 24 and 0 <= index_rate <= 1 and 0 <= protect <= 0.5):
        raise ValueError("Pitch, index rate, or protect value is out of range")
    if f0_method not in {"rmvpe", "fcpe", "crepe"}:
        raise ValueError("Unknown pitch extraction algorithm")
    if cleanup not in {"off", "light", "speech"} or not 1 <= cleanup_strength <= 30:
        raise ValueError("Unknown cleanup method or strength")
    return dict(pitch=pitch, index_rate=index_rate, protect=protect,
                f0_method=f0_method, autotune=bool(autotune), cleanup=cleanup,
                cleanup_strength=cleanup_strength)


def worker_command(mode: str, *, model_id: str, settings: dict,
                   input_path: Path | None = None, output_path: Path | None = None,
                   input_dir: Path | None = None, output_dir: Path | None = None) -> tuple[list[str], Path]:
    root = engines.applio_root()
    if root is None:
        raise engines.EngineError("APPLIO_ROOT must point to a valid Applio installation")
    model, index = engines.resolve_model(model_id)
    if mode not in {"infer", "batch"}:
        raise engines.EngineError("Unknown Applio conversion mode")
    py = os.environ.get("APPLIO_PYTHON", sys.executable)
    command = [py, str(ROOT / "scripts" / "applio_native_worker.py"), mode,
               "--root", str(root), "--model", str(model),
               "--index", str(index) if index else "",
               "--pitch", str(settings["pitch"]),
               "--index-rate", str(settings["index_rate"]),
               "--protect", str(settings["protect"]),
               "--f0-method", settings["f0_method"],
               "--cleanup", settings["cleanup"],
               "--cleanup-strength", str(settings["cleanup_strength"])]
    if settings["autotune"]:
        command.append("--autotune")
    if mode == "infer":
        if input_path is None or output_path is None:
            raise engines.EngineError("Missing source/output file")
        command += ["--input", str(input_path), "--output", str(output_path)]
    else:
        if input_dir is None or output_dir is None:
            raise engines.EngineError("Missing input/output directory")
        command += ["--input-dir", str(input_dir), "--output-dir", str(output_dir)]
    return command, root


def convert_one(*, audio: Path, model_id: str, output: Path,
                settings: dict) -> None:
    command, root = worker_command("infer", model_id=model_id, settings=settings,
                                   input_path=audio, output_path=output)
    engines._execute(command, cwd=root)
    from studio.app import _validate_output
    _validate_output(output)


def batch_convert(*, sources: list[Path], model_id: str, output: Path,
                  settings: dict) -> None:
    if not 2 <= len(sources) <= 8:
        raise engines.EngineError("Batch must have 2–8 audio files")
    source_dir = sources[0].parent
    output_dir = output.parent / "batch-output"
    output_dir.mkdir(parents=True, exist_ok=False)
    command, root = worker_command("batch", model_id=model_id, settings=settings,
                                   input_dir=source_dir, output_dir=output_dir)
    engines._execute(command, cwd=root)
    from studio.app import _validate_output
    produced = sorted(output_dir.rglob("*.wav"))
    if len(produced) != len(sources):
        raise engines.EngineError(f"Expected {len(sources)} WAV outputs, got {len(produced)}")
    for wav in produced:
        if not wav.is_file() or not wav.resolve().is_relative_to(output_dir.resolve()):
            raise engines.EngineError("Unexpected output file location")
        _validate_output(wav)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for wav in produced:
            archive.write(wav, arcname=wav.relative_to(output_dir).as_posix())
    if not output.is_file() or output.stat().st_size < 100:
        raise engines.EngineError("Batch ZIP was not created")


def blend_models(*, first: str, second: str, name: str, ratio: float) -> dict:
    root = engines.applio_root()
    if root is None:
        raise engines.EngineError("APPLIO_ROOT not configured")
    if not NEW_MODEL.fullmatch(name) or not 0 <= ratio <= 1:
        raise engines.EngineError("Invalid output model name or ratio")
    if first == second:
        raise engines.EngineError("Two different source models required")
    a, _ = engines.resolve_model(first)
    b, _ = engines.resolve_model(second)
    target = root / "logs" / f"{name}.pth"
    if target.exists():
        raise engines.EngineError("Refusing to overwrite an existing blended model")
    py = os.environ.get("APPLIO_PYTHON", sys.executable)
    command = [py, str(ROOT / "scripts" / "applio_native_worker.py"), "blend",
               "--root", str(root), "--model-a", str(a),
               "--model-b", str(b), "--name", name, "--ratio", str(ratio)]
    engines._execute(command, cwd=root)
    if not target.is_file() or target.stat().st_size < 128:
        raise engines.EngineError("No blended model checkpoint found at the expected location")
    return {"model_id": target.relative_to(root / "logs").as_posix(),
            "size_bytes": target.stat().st_size}
