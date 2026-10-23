"""Call the REAL Applio RVC core in its own environment.

API dependency: IAHispano/Applio core.run_infer_script. No fake DSP.
"""
import argparse
from pathlib import Path
import os
import sys


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--root", required=True)
    cli.add_argument("--input", required=True)
    cli.add_argument("--output", required=True)
    cli.add_argument("--model", required=True)
    cli.add_argument("--index")
    args = cli.parse_args()

    root = Path(args.root).resolve()
    os.chdir(root)
    sys.path.insert(0, str(root))
    from core import run_infer_script

    message, actual_output = run_infer_script(
        pitch=0,
        index_rate=0.3,
        volume_envelope=1.0,
        protect=0.33,
        f0_method="rmvpe",
        input_path=args.input,
        output_path=args.output,
        pth_path=args.model,
        index_path=args.index or "",
        f0_autotune=False,
        f0_autotune_strength=1.0,
        proposed_pitch=False,
        proposed_pitch_threshold=155.0,
        export_format="WAV",
    )
    if not Path(actual_output).is_file():
        raise RuntimeError("Applio returned without the expected WAV output.")
    print(message)


if __name__ == "__main__":
    main()
