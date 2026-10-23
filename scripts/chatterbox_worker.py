"""Run Chatterbox in its OWN Python environment to avoid Torch conflicts."""
import argparse
from pathlib import Path
import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--text-file", required=True)
    cli.add_argument("--output", required=True)
    cli.add_argument("--language", default="ar")
    cli.add_argument("--reference")
    cli.add_argument("--exaggeration", type=float, default=0.5)
    cli.add_argument("--cfg-weight", type=float, default=0.5)
    args = cli.parse_args()
    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    text = Path(args.text_file).read_text(encoding="utf-8")
    kwargs = {"exaggeration": args.exaggeration, "cfg_weight": args.cfg_weight}
    if args.reference:
        kwargs["audio_prompt_path"] = args.reference
    with torch.inference_mode():
        waveform = model.generate(text, language_id=args.language, **kwargs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(output), waveform.cpu(), model.sr)


if __name__ == "__main__":
    main()
