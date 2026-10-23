"""Validated, opt-in Applio RVC training CLI orchestration.

No invented checkpoint/training algorithm: runs Applio's documented
preprocess -> extract -> train commands in the separately installed runtime.
A training-ready status is NOT evidence of GPU training success.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
from typing import Callable

from studio import engines
from scripts.dataset_audit import audit_dataset

MODEL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,39}$")
MAX_STEP_SECONDS = 3 * 3600


class TrainingError(RuntimeError):
    pass


def data_dir() -> Path | None:
    value = os.getenv("APPLIO_TRAIN_DATA", "").strip()
    if not value:
        return None
    folder = Path(value).expanduser().resolve()
    return folder if folder.is_dir() else None


def status() -> dict:
    root = engines.applio_root()
    python = os.getenv("APPLIO_PYTHON", "").strip()
    if not root or not python or not engines._python_available(python):
        return {"ready": False, "reason": "Install Applio and configure APPLIO_ROOT and APPLIO_PYTHON"}
    directory = data_dir()
    if not directory:
        return {"ready": False, "reason": "Set APPLIO_TRAIN_DATA to a local private dataset directory"}
    manifest = directory / "manifest.jsonl"
    if not manifest.is_file():
        return {"ready": False, "reason": "The local dataset must include a consent manifest.jsonl"}
    try:
        audit = audit_dataset(directory, manifest)
    except (OSError, ValueError) as exc:
        return {"ready": False, "reason": f"Dataset audit failed: {exc}"}
    if not audit["ready_for_training"]:
        return {"ready": False, "reason": "Dataset audit failed: at least 10 licensed clips across train/validation/test",
                "audit": audit}
    return {"ready": True, "reason": "Local dataset audited; real model training has not yet been run",
            "clips": audit["accepted"], "minutes": audit["minutes"]}


def run_training(*, model_name: str, epochs: int, batch_size: int,
                 sample_rate: int, gpu_index: int, log: Path,
                 on_stage: Callable[[str], None]) -> dict:
    readiness = status()
    if not readiness["ready"]:
        raise TrainingError(readiness["reason"])
    if not MODEL_NAME.fullmatch(model_name):
        raise TrainingError("Model name must be 3-40 safe characters starting with a letter")
    if not 10 <= epochs <= 2000 or not 1 <= batch_size <= 16 or sample_rate not in {32000, 40000, 48000}:
        raise TrainingError("Unsupported model training parameters")
    if not 0 <= gpu_index <= 7:
        raise TrainingError("Invalid GPU index")
    root = engines.applio_root()
    dataset = data_dir()
    if (root / "logs" / model_name).exists():
        raise TrainingError("Model name already exists in Applio logs; choose a new name")
    python = os.environ["APPLIO_PYTHON"].strip()
    shared = ["--model-name", model_name]
    stages = [
        ("preprocess", ["preprocess", *shared, "--dataset-path", str(dataset),
                        "--sample-rate", str(sample_rate), "--cpu-cores", "4"]),
        ("extract", ["extract", *shared, "--sample-rate", str(sample_rate),
                     "--f0-method", "rmvpe", "--cpu-cores", "4",
                     "--gpu", str(gpu_index)]),
        ("train", ["train", *shared, "--sample-rate", str(sample_rate),
                   "--save-every-epoch", "5", "--total-epoch", str(epochs),
                   "--batch-size", str(batch_size), "--gpu", str(gpu_index)]),
    ]
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as writer:
        for label, options in stages:
            on_stage(label)
            writer.write(f"\n--- {label} ---\n")
            writer.flush()
            try:
                result = subprocess.run(
                    [python, str(root / "core.py"), *options],
                    cwd=str(root), stdout=writer, stderr=subprocess.STDOUT,
                    timeout=MAX_STEP_SECONDS, check=False)
            except subprocess.TimeoutExpired as exc:
                raise TrainingError(f"Applio {label} timed out; see training log") from exc
            except OSError as exc:
                raise TrainingError(f"Applio {label} could not start: {exc}") from exc
            if result.returncode:
                raise TrainingError(f"Applio {label} exited with code {result.returncode}; see training log")
    # A zero exit code alone does not prove training created a model.
    checkpoint_root = root / "logs" / model_name
    weights_root = root / "assets" / "weights"
    checkpoints = list(checkpoint_root.rglob("*.pth")) if checkpoint_root.is_dir() else []
    if weights_root.is_dir():
        checkpoints += list(weights_root.glob(model_name + "*.pth"))
    if not any(path.is_file() and path.stat().st_size > 0 for path in checkpoints):
        raise TrainingError("CLI returned success but no RVC checkpoint was found; inspect training log.")
    return {"model_name": model_name, "sample_rate": sample_rate,
            "epochs": epochs, "checkpoint_count": len(checkpoints), "stages": [name for name, _ in stages],
            "note": "Applio CLI steps returned success; verify the generated model and listen to outputs before release."}
