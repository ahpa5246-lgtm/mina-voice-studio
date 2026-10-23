"""Local cartoon production: consented character voice profiles and episode assembly.

No invented timbres. Each distinct identity requires a distinct authorized
reference recording or appropriately licensed pre-trained voice model.
All audio frames in an episode are produced by the actual configured engine.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
import wave

from studio import engines
from studio.subtitles import subtitle_text
from studio.text import normalize_text

MAX_CHARACTERS = 128
MAX_LINES = 48
MAX_LINE_CHARS = 500
MAX_TOTAL_CHARS = 6000
MAX_EPISODE_BYTES = 180 * 1024 * 1024
ID = re.compile(r"^[a-f0-9]{32}$")
LANGUAGES = set("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split())
MODELS = {"multilingual-v3", "turbo", "nano", "qwen-clone", "qwen-custom"}
QWEN_LANGUAGE = {"en":"English","zh":"Chinese","ja":"Japanese","ko":"Korean","de":"German","fr":"French","ru":"Russian","pt":"Portuguese","es":"Spanish","it":"Italian"}
QWEN_SPEAKERS = {"Vivian","Serena","Uncle_Fu","Dylan","Eric","Ryan","Aiden","Ono_Anna","Sohee"}
DELIVERY = {
    # Approximate Chatterbox conditioning parameters, not discrete emotion synthesis.
    "neutral": (0.0, 0.0),
    "energetic": (0.20, -0.12),
    "sarcastic": (-0.03, -0.12),
    "quiet": (-0.12, 0.12),
    "dramatic": (0.24, -0.18),
    "angry": (0.25, -0.20),
    "sad": (-0.10, 0.12),
    "crying": (0.22, -0.20),
}


def storage(root: Path) -> Path:
    target = root / "_cast"
    target.mkdir(parents=True, exist_ok=True)
    return target


def validate_character(name: str, voice_id: str, model: str, language: str,
                       exaggeration: float, cfg_weight: float,
                       speaker: str = "Ryan", reference_text: str = "") -> dict:
    name = name.strip()
    if not name or len(name) > 72 or any(ord(c) < 32 for c in name):
        raise ValueError("Character name must have 1-72 printable characters")
    if voice_id and not ID.fullmatch(voice_id):
        raise ValueError("Invalid reference recording identifier")
    if model not in MODELS or language not in LANGUAGES:
        raise ValueError("Unknown voice model or language")
    if model in {"turbo","nano"} and (language != "en" or not voice_id):
        raise ValueError("Turbo/Nano require English and an authorized voice reference")
    if model in {"qwen-clone","qwen-custom"} and language not in QWEN_LANGUAGE:
        raise ValueError("Official Qwen3-TTS does not support Arabic")
    if model == "qwen-clone" and (not voice_id or not 3 <= len(reference_text.strip()) <= 500):
        raise ValueError("Qwen clone needs a reference WAV and its exact transcript")
    if model == "qwen-custom" and speaker not in QWEN_SPEAKERS:
        raise ValueError("Select an official Qwen preset speaker")
    if len(reference_text) > 500:
        raise ValueError("Reference transcript exceeds 500 characters")
    if not 0.25 <= exaggeration <= 1.0 or not 0 <= cfg_weight <= 1:
        raise ValueError("Invalid expressiveness or guidance")
    return {"name": name, "voice_id": voice_id, "model": model,
            "language": language, "exaggeration": exaggeration,
            "cfg_weight": cfg_weight, "speaker": speaker,
            "reference_text": reference_text.strip()}


def all_characters(root: Path) -> list[dict]:
    result = []
    for file in sorted(storage(root).glob("*.json")):
        if not ID.fullmatch(file.stem):
            continue
        try:
            profile = json.loads(file.read_text(encoding="utf-8"))
            if profile.get("id") != file.stem:
                continue
            validate_character(
                profile["name"], profile["voice_id"], profile["model"],
                profile["language"], profile["exaggeration"], profile["cfg_weight"],
                profile.get("speaker","Ryan"), profile.get("reference_text",""))
            result.append(profile)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return result


def get_character(root: Path, identifier: str) -> dict:
    if not ID.fullmatch(identifier):
        raise ValueError("Character not found")
    for profile in all_characters(root):
        if profile["id"] == identifier:
            return profile
    raise ValueError("Character not found")


def create_character(root: Path, *, name: str, voice_id: str = "",
                     model: str = "multilingual-v3", language: str = "ar",
                     exaggeration: float = 0.5, cfg_weight: float = 0.5,
                     speaker: str = "Ryan", reference_text: str = "") -> dict:
    valid = validate_character(name, voice_id, model, language, exaggeration, cfg_weight,
                               speaker, reference_text)
    if len(all_characters(root)) >= MAX_CHARACTERS:
        raise ValueError("Character profile capacity reached (128).")
    profile = {"id": uuid4().hex, **valid}
    destination = storage(root) / (profile["id"] + ".json")
    destination.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    return profile


def delete_character(root: Path, identifier: str) -> None:
    get_character(root, identifier)
    (storage(root) / (identifier + ".json")).unlink()


def validate_script(root: Path, entries: object) -> list[dict]:
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_LINES:
        raise ValueError("Episode must contain between 1 and 48 dialogue lines.")
    prepared = []
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Every dialogue line must be an object.")
        profile = get_character(root, str(entry.get("character_id", "")))
        text = normalize_text(str(entry.get("text", "")))
        if not 1 <= len(text) <= MAX_LINE_CHARS:
            raise ValueError("Each line must contain 1-500 characters.")
        mood = str(entry.get("delivery", "neutral"))
        if mood not in DELIVERY:
            raise ValueError("Unrecognized performance direction.")
        pause_ms = entry.get("pause_ms", 250)
        if type(pause_ms) is not int or not 0 <= pause_ms <= 2000:
            raise ValueError("Pause must be an integer between 0 and 2000 ms.")
        total += len(text)
        if total > MAX_TOTAL_CHARS:
            raise ValueError("Episode is limited to 6,000 characters.")
        prepared.append({
            "character": profile,
            "text": text,
            "delivery": mood,
            "pause_ms": pause_ms,
        })
    return prepared


def _read_wav(path: Path) -> tuple[bytes, int, int]:
    with wave.open(str(path), "rb") as source:
        rate, channels, width = source.getframerate(), source.getnchannels(), source.getsampwidth()
        if source.getcomptype() != "NONE" or width != 2 or channels not in (1, 2):
            raise ValueError("Episode assembly requires uncompressed mono/stereo PCM16 WAV.")
        if not 8000 <= rate <= 192000 or not source.getnframes():
            raise ValueError("Invalid rendered voice WAV sample rate or length.")
        content = source.readframes(source.getnframes())
    return content, rate, channels


def assemble_episode(lines: list[dict], wav_files: list[Path], directory: Path) -> dict:
    """Combine actual voice renders without changing pitch/tempo or inventing sound."""
    if not lines or len(lines) != len(wav_files):
        raise ValueError("Missing rendered dialogue clips.")
    output = directory / "output.wav"
    manifest = []
    subtitles = []
    rate = channels = None
    frame_position = 0
    written = 0
    with wave.open(str(output), "wb") as merged:
        for i, (line, path) in enumerate(zip(lines, wav_files)):
            samples, sample_rate, ch = _read_wav(path)
            if rate is None:
                rate, channels = sample_rate, ch
                merged.setnchannels(channels)
                merged.setsampwidth(2)
                merged.setframerate(rate)
            if sample_rate != rate or ch != channels:
                # All output remains PCM16; Python 3.11/3.12 audioop does not alter pitch.
                import audioop
                if ch != channels:
                    samples = (audioop.tomono(samples,2,.5,.5) if ch == 2
                               else audioop.tostereo(samples,2,1,1))
                    ch = channels
                if sample_rate != rate:
                    samples = audioop.ratecv(samples,2,channels,sample_rate,rate,None)[0]
            written += len(samples)
            if written > MAX_EPISODE_BYTES:
                raise ValueError("Episode WAV exceeds allowed size.")
            begin = frame_position / rate
            merged.writeframesraw(samples)
            frame_position += len(samples) // (channels * 2)
            end = frame_position / rate
            profile = line["character"]
            subtitles.append({"start": begin, "end": end,
                              "text": f'{profile["name"]}: {line["text"]}'})
            manifest.append({
                "line": i + 1, "character_id": profile["id"],
                "character": profile["name"], "voice_model": profile["model"],
                "delivery": line["delivery"], "text": line["text"],
                "start_seconds": round(begin, 3), "end_seconds": round(end, 3),
                "clip": f"lines/line-{i+1:03}.wav",
            })
            silence_frames = int(round(rate * line["pause_ms"] / 1000)) if i + 1 < len(lines) else 0
            if silence_frames:
                silence = b"\0" * (silence_frames * channels * 2)
                written += len(silence)
                if written > MAX_EPISODE_BYTES:
                    raise ValueError("Episode exceeds maximum size.")
                merged.writeframesraw(silence)
                frame_position += silence_frames
    (directory / "dialogue.srt").write_text(subtitle_text(subtitles, "srt"), encoding="utf-8")
    details = {"lines": manifest, "duration_seconds": round(frame_position / rate, 3),
               "sample_rate": rate, "channels": channels,
               "note": "Line delivery settings approximate emotion; audition the output."}
    (directory / "manifest.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = directory / "episode.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        bundle.write(output, "episode.wav")
        bundle.write(directory / "dialogue.srt", "dialogue.srt")
        bundle.write(directory / "manifest.json", "manifest.json")
        for i, path in enumerate(wav_files, 1):
            bundle.write(path, f"lines/line-{i:03}.wav")
    if archive.stat().st_size < 100:
        raise ValueError("No usable episode archive produced.")
    return details


def render_episode(root: Path, directory: Path, script: list[dict],
                   resolve_reference, on_line) -> dict:
    """Every spoken line is synthesized for real; never reuse a mock audio file."""
    directory.mkdir(parents=True, exist_ok=True)
    renders = []
    for index, line in enumerate(script):
        profile = line["character"]
        voice_id = profile["voice_id"]
        reference = resolve_reference(voice_id) if voice_id else None
        if profile["model"] in {"turbo","nano","qwen-clone"} and reference is None:
            raise ValueError("This character needs a real reference recording.")
        direction = DELIVERY[line["delivery"]]
        exaggeration = min(1.0, max(0.25, profile["exaggeration"] + direction[0]))
        cfg_weight = min(1.0, max(0, profile["cfg_weight"] + direction[1]))
        text_file = directory / f"line-{index+1:03}.txt"
        target = directory / f"line-{index+1:03}.wav"
        text_file.write_text(line["text"], encoding="utf-8")
        on_line(index + 1, len(script))
        if profile["model"].startswith("qwen-"):
            from studio.qwen_runtime import synthesize
            acting = {
                "neutral":"",
                "energetic":"Speak with animated excitement and lively pacing.",
                "sarcastic":"Deliver the words with dry, skeptical sarcasm.",
                "quiet":"Speak quietly with warm, restrained emotion.",
                "dramatic":"Speak theatrically with expressive pauses.",
                "angry":"Speak with audible frustration and anger.",
                "sad":"Speak in a subdued, sad tone.",
                "crying":"Speak tearfully, with a trembling emotional tone.",
            }
            # Qwen Base clone does not support the acting instruct argument;
            # expressive per-line prompts are available for fixed preset speakers.
            synthesize(text_file=text_file,output=target,
                       mode="clone" if profile["model"]=="qwen-clone" else "custom",
                       language=QWEN_LANGUAGE[profile["language"]],
                       speaker=profile.get("speaker","Ryan"),
                       ref_audio=reference,
                       ref_text=profile.get("reference_text",""),
                       instruct=(acting[line["delivery"]] if profile["model"]=="qwen-custom" else ""))
        else:
            engines.synthesize(
                text_file=text_file, output=target, language=profile["language"],
                reference=reference, model=profile["model"],
                exaggeration=exaggeration, cfg_weight=cfg_weight)
        _read_wav(target)  # Fail now, not after marking the episode complete.
        renders.append(target)
    return assemble_episode(script, renders, directory)
