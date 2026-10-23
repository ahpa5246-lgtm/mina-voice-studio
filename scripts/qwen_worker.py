"""Official Qwen3-TTS APIs: voice design, reusable reference cloning, acted preset speakers.
Separate Python process and environment. No model weights are redistributed.
"""
import argparse
from contextlib import redirect_stdout
import gc
import json
from pathlib import Path
import sys

MODELS={
 "design":"Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
 "clone":"Qwen/Qwen3-TTS-12Hz-1.7B-Base",
 "custom":"Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
}
LANGUAGES=set("English Chinese Japanese Korean German French Russian Portuguese Spanish Italian".split())
SPEAKERS={"Vivian","Serena","Uncle_Fu","Dylan","Eric","Ryan","Aiden","Ono_Anna","Sohee"}
ALLOWED={"mode","text","output","language","instruct","ref_audio","ref_text","speaker"}
class EngineCache:
    def __init__(self):
        self.name=None
        self.model=None
        self.prompt_cache={}
    def load(self,mode):
        if mode not in MODELS:
            raise ValueError("Unsupported Qwen model mode")
        if self.name==mode and self.model is not None:
            return self.model
        if self.model is not None:
            self.model=None
            self.prompt_cache.clear()
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        import torch
        from qwen_tts import Qwen3TTSModel
        cuda=torch.cuda.is_available()
        dtype=(torch.bfloat16 if cuda and torch.cuda.is_bf16_supported()
               else torch.float16 if cuda else torch.float32)
        self.model=Qwen3TTSModel.from_pretrained(
           MODELS[mode], device_map="cuda:0" if cuda else "cpu",
           dtype=dtype, attn_implementation="sdpa")
        self.name=mode
        return self.model
    def prompt(self,model,ref_audio,ref_text):
        key=(str(Path(ref_audio).resolve()),ref_text)
        if key not in self.prompt_cache:
            self.prompt_cache[key]=model.create_voice_clone_prompt(
              ref_audio=ref_audio,ref_text=ref_text,x_vector_only_mode=False)
            if len(self.prompt_cache)>32:
                self.prompt_cache.pop(next(iter(self.prompt_cache)))
        return self.prompt_cache[key]

def synthesize(spec,cache):
    if not isinstance(spec,dict) or set(spec)-ALLOWED:
        raise ValueError("Unexpected Qwen request fields")
    mode=spec.get("mode","")
    if mode not in MODELS:
        raise ValueError("Unsupported model mode")
    text=spec.get("text","").strip()
    language=spec.get("language","English")
    instruction=spec.get("instruct","")
    if language not in LANGUAGES:
        raise ValueError("Qwen3 12Hz has no official Arabic voice generation")
    if not 1<=len(text)<=600 or len(instruction)>800:
        raise ValueError("Invalid script or acting instruction length")
    if mode=="design" and len(instruction.strip())<8:
        raise ValueError("Voice description must be at least eight characters")
    if mode=="custom" and spec.get("speaker","") not in SPEAKERS:
        raise ValueError("Unknown fixed character voice")
    if mode=="clone":
        if not Path(spec.get("ref_audio","")).is_file() or len(spec.get("ref_text","").strip())<3:
            raise ValueError("Qwen clone requires an existing seed clip and exact transcript")
    import numpy as np
    import soundfile as sf
    model=cache.load(mode)
    if mode=="design":
        wavs,sr=model.generate_voice_design(text=text,language=language,instruct=instruction)
    elif mode=="custom":
        wavs,sr=model.generate_custom_voice(
            text=text,language=language,speaker=spec["speaker"],instruct=instruction)
    else:
        prompt=cache.prompt(model,spec["ref_audio"],spec["ref_text"])
        wavs,sr=model.generate_voice_clone(
           text=text,language=language,voice_clone_prompt=prompt)
    if len(wavs)!=1:
        raise RuntimeError("Expected one speech waveform")
    wav=np.asarray(wavs[0],dtype=np.float32).reshape(-1)
    if not 8000<=sr<=192000 or not 1<=wav.size<=sr*180:
        raise RuntimeError("Invalid speech duration or sample rate")
    if not np.isfinite(wav).all() or np.max(np.abs(wav))>1.2:
        raise RuntimeError("Non-finite or severely clipped speech")
    out=Path(spec["output"])
    out.parent.mkdir(parents=True,exist_ok=True)
    sf.write(str(out),wav.clip(-1,1),int(sr),subtype="PCM_16")

def serve():
    cache=EngineCache()
    for line in sys.stdin:
        try:
            obj=json.loads(line)
            if obj=={"action":"ping"}:
                result={"ok":True,"loaded":cache.name}
            elif obj=={"action":"stop"}:
                result={"ok":True,"stopped":True}
            else:
                with redirect_stdout(sys.stderr):
                    synthesize(obj,cache)
                result={"ok":True}
        except Exception as exc:
            result={"ok":False,"error":str(exc)[:750]}
        sys.stdout.write(json.dumps(result,ensure_ascii=False)+"\n")
        sys.stdout.flush()
        if result.get("stopped"):
            return

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--serve-stdio",action="store_true")
    parser.add_argument("--request")
    args=parser.parse_args()
    if args.serve_stdio:
        serve()
    elif args.request:
        spec=json.loads(Path(args.request).read_text(encoding="utf-8"))
        synthesize(spec,EngineCache())
    else:
        parser.error("Specify --request or --serve-stdio")

if __name__=="__main__":
    main()
