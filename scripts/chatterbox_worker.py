"""Real Resemble AI Chatterbox V3, Turbo and Nano worker (MIT upstream)."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
MODELS = {"multilingual-v3", "turbo", "nano"}
LANGUAGES = set("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split())

class Cache:
    def __init__(self):
        self.model = None
        self.name = None
        self.default_conditionals = None

    def get(self, name):
        if name not in MODELS:
            raise ValueError("Unknown model")
        import torch
        if name == self.name and self.model is not None:
            return self.model, torch
        if self.model is not None:
            self.model = None
            self.name = None
            self.default_conditionals = None
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        if name == "multilingual-v3":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
        else:
            from chatterbox.tts_turbo import ChatterboxTurboTTS
            model = ChatterboxTurboTTS.from_pretrained(device=device, nano=(name == "nano"))
        if name == "multilingual-v3":
            import copy
            self.default_conditionals = copy.deepcopy(model.conds)
        self.model, self.name = model, name
        return model, torch

def render(*, text_file, output, language="ar", reference=None,
           model_name="multilingual-v3", exaggeration=.5, cfg_weight=.5, cache=None):
    from studio.text import normalize_text, split_speech
    import torchaudio as ta
    if model_name not in MODELS or language not in LANGUAGES:
        raise ValueError("Unsupported model or language")
    if model_name != "multilingual-v3" and language != "en":
        raise ValueError("Turbo and Nano only support English")
    if model_name != "multilingual-v3" and not reference:
        raise ValueError("Turbo and Nano require an authorized voice reference")
    if not .25 <= exaggeration <= 1 or not 0 <= cfg_weight <= 1:
        raise ValueError("Invalid voice controls")
    text = normalize_text(Path(text_file).read_text(encoding="utf-8"))
    if not 1 <= len(text) <= 6000:
        raise ValueError("Text must be 1 to 6000 characters")
    cache = cache or Cache()
    model, torch = cache.get(model_name)
    settings = {}
    if model_name == "multilingual-v3":
        settings = {"exaggeration": exaggeration, "cfg_weight": cfg_weight}
        if reference:
            model.prepare_conditionals(str(reference), exaggeration=exaggeration)
        else:
            # Reset the built-in speaker after a prior job cloned another voice.
            # Never accidentally reuse a different user\x27s reference embedding.
            import copy
            model.conds = copy.deepcopy(cache.default_conditionals)
    else:
        settings = {"audio_prompt_path": str(reference)}
    waves = []
    sr = int(model.sr)
    with torch.inference_mode():
        for i, chunk in enumerate(split_speech(text)):
            wave = (model.generate(chunk, language_id=language, **settings)
                    if model_name == "multilingual-v3" else model.generate(chunk, **settings))
            wave = wave.detach().cpu()
            if wave.ndim != 2 or wave.shape[0] != 1 or wave.shape[1] < 1:
                raise RuntimeError("Invalid Chatterbox tensor")
            if not torch.isfinite(wave).all():
                raise RuntimeError("Non-finite audio samples")
            fade = min(int(sr*.01), wave.shape[1]//2)
            if fade:
                wave[:, :fade] *= torch.linspace(0,1,fade,dtype=wave.dtype).unsqueeze(0)
                wave[:, -fade:] *= torch.linspace(1,0,fade,dtype=wave.dtype).unsqueeze(0)
            if i:
                waves.append(torch.zeros((1,int(sr*.14)),dtype=wave.dtype))
            waves.append(wave)
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    ta.save(str(target),torch.cat(waves,dim=1),sr,format="wav")
    return {"model":model_name,"chunks":len(waves),"sample_rate":sr}

def serve():
    cache=Cache()
    for line in sys.stdin:
        try:
            job=json.loads(line)
            if job.get("operation")=="ping":
                reply={"ok":True,"cached_model":cache.name}
            elif job.get("operation")=="synthesize":
                with redirect_stdout(sys.stderr):
                    details=render(cache=cache,**job["args"])
                reply={"ok":True,"details":details}
            elif job.get("operation")=="stop":
                reply={"ok":True,"stopped":True}
            else:
                raise ValueError("Unknown operation")
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            reply={"ok":False,"error":str(error)[:800]}
        sys.stdout.write(json.dumps(reply,ensure_ascii=False)+"\n")
        sys.stdout.flush()
        if reply.get("stopped"):
            break

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--serve-stdio",action="store_true")
    p.add_argument("--text-file")
    p.add_argument("--output")
    p.add_argument("--language",default="ar")
    p.add_argument("--reference")
    p.add_argument("--model",default="multilingual-v3",choices=sorted(MODELS))
    p.add_argument("--exaggeration",type=float,default=.5)
    p.add_argument("--cfg-weight",type=float,default=.5)
    a=p.parse_args()
    if a.serve_stdio:
        serve()
        return
    if not a.text_file or not a.output:
        p.error("text file and output required")
    with redirect_stdout(sys.stderr):
        render(text_file=a.text_file,output=a.output,language=a.language,
               reference=a.reference,model_name=a.model,
               exaggeration=a.exaggeration,cfg_weight=a.cfg_weight)

if __name__=="__main__":
    main()
