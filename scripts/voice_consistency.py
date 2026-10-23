"""Optional, real speaker-embedding evaluation of exported cartoon episodes.

Runs pretrained Resemblyzer GE2E (English-biased) only when installed. It is
an *estimate*, not proof of identity or emotional naturalness.
"""
from __future__ import annotations
from itertools import combinations
import json
from pathlib import Path
import statistics
import tempfile
from zipfile import ZipFile

def _cosine(a,b):
    import numpy as np
    denom=float(np.linalg.norm(a)*np.linalg.norm(b))
    if denom < 1e-10:
        raise ValueError("Speaker embedding had zero norm")
    return float(np.dot(a,b)/denom)


def evaluate_archive(source:Path, encoder=None) -> dict:
    from resemblyzer import VoiceEncoder, preprocess_wav
    encoder=encoder or VoiceEncoder(device="cpu")
    grouped={}
    with ZipFile(source) as archive:
        manifest=json.loads(archive.read("manifest.json"))
        rows=manifest.get("lines",[])
        if not 1<=len(rows)<=48:
            raise ValueError("Episode requires 1–48 real clips")
        for row in rows:
            clip=row.get("clip","")
            # Only referenced generated line clips; never allow archive traversal.
            if not clip.startswith("lines/line-") or not clip.endswith(".wav") or ".." in clip:
                raise ValueError("Unsafe clip in episode manifest")
            raw=archive.read(clip)
            if len(raw)>20*1024*1024:
                raise ValueError("A single line exceeds the evaluator limit")
            with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                tmp.write(raw);tmp.flush()
                samples=preprocess_wav(Path(tmp.name))
                if samples.size<16000:
                    raise ValueError("Clip is too short for a meaningful voice embedding")
                vector=encoder.embed_utterance(samples)
            grouped.setdefault(row["character_id"],[]).append((row["character"],vector))
    within=[]
    between=[]
    embeddings={speaker:[vector for _,vector in rows] for speaker,rows in grouped.items()}
    for speaker,vectors in embeddings.items():
        for a,b in combinations(vectors,2):
            within.append(_cosine(a,b))
    for left,right in combinations(embeddings.values(),2):
        for a in left:
            for b in right:
                between.append(_cosine(a,b))
    return {
        "characters":len(embeddings),
        "lines":sum(len(rows) for rows in embeddings.values()),
        "within_character_pairs":len(within),
        "within_character_mean_cosine":round(statistics.mean(within),4) if within else None,
        "within_character_min_cosine":round(min(within),4) if within else None,
        "between_character_pairs":len(between),
        "between_character_mean_cosine":round(statistics.mean(between),4) if between else None,
        "separation_margin":round(statistics.mean(within)-statistics.mean(between),4)
              if within and between else None,
        "interpretation":"Speaker-embedding estimates only. High within and lower between "
            "similarity suggest consistency, but the embedding model is not validated "
            "for every cartoon/accent/emotional delivery. Use blind listening tests.",
        "passed":None,
    }


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("episode_zip",type=Path)
    parser.add_argument("--output",type=Path,default=None)
    args=parser.parse_args()
    report=evaluate_archive(args.episode_zip)
    result=json.dumps(report,indent=2,ensure_ascii=False)
    if args.output:args.output.write_text(result,encoding="utf-8")
    print(result)


if __name__=="__main__":
    main()
