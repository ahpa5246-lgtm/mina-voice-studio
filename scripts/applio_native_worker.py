"""Invoke ORIGINAL Applio core functionality from its isolated Python runtime.

Source/API: https://github.com/IAHispano/Applio (MIT).
No copies of proprietary weights; no simulated voice output.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys


def common_args(parser):
    parser.add_argument("--root", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--index", default="")
    parser.add_argument("--pitch", type=int, default=0)
    parser.add_argument("--index-rate", type=float, default=0.3)
    parser.add_argument("--protect", type=float, default=0.33)
    parser.add_argument("--f0-method", choices=["rmvpe", "fcpe", "crepe"], default="rmvpe")
    parser.add_argument("--autotune", action="store_true")
    parser.add_argument("--cleanup", choices=["off", "light", "speech"], default="off")
    parser.add_argument("--cleanup-strength", type=float, default=12)


def _inference_kwargs(args):
    if not -24 <= args.pitch <= 24:
        raise ValueError("Pitch must be between -24 and 24")
    if not 0 <= args.index_rate <= 1 or not 0 <= args.protect <= 0.5:
        raise ValueError("Invalid index/protect ratio")
    if not 1 <= args.cleanup_strength <= 30:
        raise ValueError("Invalid cleanup intensity")
    return dict(
        pitch=args.pitch, index_rate=args.index_rate, volume_envelope=1.0,
        protect=args.protect, f0_method=args.f0_method, pth_path=args.model,
        index_path=args.index, f0_autotune=args.autotune, f0_autotune_strength=1.0,
        proposed_pitch=False, proposed_pitch_threshold=155.0, export_format="WAV",
        embedder_model="contentvec", embedder_model_custom=None,
        cleanup_mode=args.cleanup, cleanup_strength=args.cleanup_strength,
    )


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    infer = sub.add_parser("infer")
    common_args(infer)
    infer.add_argument("--input", required=True)
    infer.add_argument("--output", required=True)
    batch = sub.add_parser("batch")
    common_args(batch)
    batch.add_argument("--input-dir", required=True)
    batch.add_argument("--output-dir", required=True)
    blend = sub.add_parser("blend")
    blend.add_argument("--root", required=True)
    blend.add_argument("--model-a", required=True)
    blend.add_argument("--model-b", required=True)
    blend.add_argument("--name", required=True)
    blend.add_argument("--ratio", type=float, required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not (root / "core.py").is_file():
        raise RuntimeError("Valid original Applio installation not found")
    os.chdir(root)
    sys.path.insert(0, str(root))
    if args.mode == "blend":
        from core import run_model_blender_script
        if not 0 <= args.ratio <= 1:
            raise ValueError("Blend ratio out of range")
        msg, path = run_model_blender_script(args.name, args.model_a, args.model_b, args.ratio)
        if not path or not Path(path).is_file() or Path(path).stat().st_size < 128:
            raise RuntimeError(f"Upstream model blend failed: {msg}")
        print(msg, flush=True)
        return

    kwargs = _inference_kwargs(args)
    if args.mode == "infer":
        from core import run_infer_script
        message, generated = run_infer_script(
            input_path=args.input, output_path=args.output,
            **kwargs,
        )
        if not Path(generated).is_file() or Path(generated).stat().st_size < 44:
            raise RuntimeError("Applio reported success but did not generate WAV.")
        print(message, flush=True)
        return

    from core import run_batch_infer_script
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    print(run_batch_infer_script(
        input_folder=args.input_dir,
        output_folder=args.output_dir,
        **kwargs,
    ), flush=True)


if __name__ == "__main__":
    main()
