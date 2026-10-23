"""Generate real, long-form multilingual TTS in an isolated Python environment.

Loads model once per job and renders segmented text to a single WAV.
All generated segments retain upstream neural watermarking.
"""
import argparse
from pathlib import Path
import sys

# Ensure the workspace text-normalization module is available in the model venv.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torchaudio as ta

from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from studio.text import MAX_DOCUMENT_CHARS, split_speech


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--language", default="ar")
    parser.add_argument("--reference")
    parser.add_argument("--exaggeration", type=float, default=0.5)
    parser.add_argument("--cfg-weight", type=float, default=0.5)
    args = parser.parse_args()

    text = Path(args.text_file).read_text(encoding="utf-8")
    if not text.strip() or len(text) > MAX_DOCUMENT_CHARS:
        raise ValueError(f"Text must contain 1-{MAX_DOCUMENT_CHARS} characters.")
    segments = split_speech(text)
    if not segments:
        raise ValueError("No speakable text.")

    device = ("cuda" if torch.cuda.is_available()
              else "mps" if torch.backends.mps.is_available() else "cpu")
    model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    kwargs = {"exaggeration": args.exaggeration, "cfg_weight": args.cfg_weight}
    if args.reference:
        kwargs["audio_prompt_path"] = args.reference

    waveforms = []
    silence_samples = int(model.sr * 0.14)
    with torch.inference_mode():
        for i, segment in enumerate(segments):
            print(f"Rendering segment {i + 1}/{len(segments)} ({len(segment)} characters)", flush=True)
            wav = model.generate(segment, language_id=args.language, **kwargs).detach().cpu()
            if wav.ndim != 2 or wav.shape[0] != 1 or wav.shape[1] == 0:
                raise RuntimeError("Model produced an invalid audio tensor.")
            if not torch.isfinite(wav).all():
                raise RuntimeError("Model produced a non-finite audio tensor.")
            if i:
                waveforms.append(torch.zeros((1, silence_samples), dtype=wav.dtype))
            waveforms.append(wav)
    audio = torch.cat(waveforms, dim=1)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    ta.save(str(out), audio, model.sr, format="wav")


if __name__ == "__main__":
    main()
