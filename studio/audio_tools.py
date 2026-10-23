"""Pure-Python, deterministic PCM-16 audio processing, never a fake AI model."""
from __future__ import annotations
from array import array
from math import cos, pi, sqrt
from pathlib import Path
import sys
import wave


def _load_pcm16(path: Path) -> tuple[array, int, int]:
    with wave.open(str(path), "rb") as reader:
        channels, rate, width = reader.getnchannels(), reader.getframerate(), reader.getsampwidth()
        if reader.getcomptype() != "NONE" or width != 2 or channels not in (1, 2):
            raise ValueError("Enhancement accepts mono/stereo uncompressed PCM-16 WAV only.")
        if not 8000 <= rate <= 192000 or not reader.getnframes():
            raise ValueError("Invalid audio sample rate or empty WAV.")
        if reader.getnframes() > rate * 15 * 60:
            raise ValueError("WAV exceeds 15 minute limit.")
        samples = array("h")
        samples.frombytes(reader.readframes(reader.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples, channels, rate


def enhance_wav(*, audio: Path, output: Path, highpass_hz: float = 65.0,
                peak_dbfs: float = -1.0, noise_gate: bool = False) -> None:
    """High-pass filter + safe peak-normalization + optional gentle RMS noise gate.

    Not neural denoising; purpose is reliable, low-dependency speech cleanup.
    """
    if not 0 <= highpass_hz <= 200 or not -18 <= peak_dbfs <= -0.5:
        raise ValueError("Invalid enhancement parameters.")
    data, channels, rate = _load_pcm16(audio)
    alpha = 1 / (1 + 2 * pi * highpass_hz / rate) if highpass_hz else 0
    prev_input = [0.0] * channels
    prev_output = [0.0] * channels
    filtered = array("f")
    for i, sample in enumerate(data):
        channel = i % channels
        x = float(sample)
        if highpass_hz:
            y = alpha * (prev_output[channel] + x - prev_input[channel])
            prev_input[channel] = x
            prev_output[channel] = y
        else:
            y = x
        filtered.append(y)
    if noise_gate:
        # Gate windows of 20ms, preserving loud speech and softening the
        # transition between silent and voiced areas.
        chunk = max(1, int(rate * .02))
        previous_gain = 1.0
        for start in range(0, len(filtered), chunk * channels):
            end = min(len(filtered), start + chunk * channels)
            segment = filtered[start:end]
            rms = sqrt(sum(v * v for v in segment) / len(segment))
            target = 0.12 if rms < 145 else 1.0
            # 0.35 attack/release smoothing avoids sharp click discontinuities.
            gain = (previous_gain + target) / 2
            for j in range(start, end):
                filtered[j] *= gain
            previous_gain = gain
    peak = max((abs(x) for x in filtered), default=0.0)
    target_peak = 32767 * 10 ** (peak_dbfs / 20)
    gain = min(target_peak / peak, 20.0) if peak else 1.0
    result = array("h")
    for value in filtered:
        x = int(round(value * gain))
        result.append(max(-32768, min(32767, x)))
    if sys.byteorder != "little":
        result.byteswap()
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(result.tobytes())
