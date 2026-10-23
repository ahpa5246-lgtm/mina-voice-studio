"""Convert the real Faster-Whisper timestamps to SRT and WebVTT."""
from __future__ import annotations
import math

def _stamp(seconds: float, separator: str) -> str:
    if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 359999:
        raise ValueError("Invalid subtitle timestamp")
    milli = round(seconds * 1000)
    hours, milli = divmod(milli, 3600000)
    minutes, milli = divmod(milli, 60000)
    secs, milli = divmod(milli, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milli:03d}"

def subtitle_text(segments: list[dict], fmt: str = "srt") -> str:
    if fmt not in {"srt", "vtt"}:
        raise ValueError("Unsupported subtitle format")
    if not isinstance(segments, list) or len(segments) > 10000:
        raise ValueError("Invalid subtitle segments")
    output = ["WEBVTT", ""] if fmt == "vtt" else []
    for number, segment in enumerate(segments, 1):
        start, end = segment["start"], segment["end"]
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
            raise ValueError("Invalid subtitle duration")
        text = " ".join(str(segment["text"]).split())
        if not text or len(text) > 1000:
            raise ValueError("Invalid subtitle text")
        sep = "." if fmt == "vtt" else ","
        if fmt == "srt":
            output.append(str(number))
        output.extend([f"{_stamp(start,sep)} --> {_stamp(end,sep)}", text, ""])
    return "\n".join(output)
