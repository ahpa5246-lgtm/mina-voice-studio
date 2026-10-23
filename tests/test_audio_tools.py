"""1000 distinct deterministic signal-processing regression cases plus edge cases."""
from array import array
import io
import math
import random
import sys
from pathlib import Path
import wave

import pytest

from studio.audio_tools import enhance_wav


def make_wav(path: Path, samples: list[int], channels: int = 1, rate: int = 16000):
    vals = array("h", samples)
    if sys.byteorder != "little":
        vals.byteswap()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(vals.tobytes())


@pytest.mark.parametrize("case", range(1000))
def test_1000_distinct_wav_processing_inputs(case, tmp_path):
    """A real DSP pass for every case; different lengths, channels, gains, gate, filters."""
    rng = random.Random(case + 4137)
    channels = 1 if case % 3 else 2
    frames = 60 + (case * 11) % 260
    samples = [
        int(rng.randint(-25000, 25000) * (.05 if case % 5 == 0 else 1))
        for _ in range(frames * channels)
    ]
    if case % 43 == 0:
        samples = [0] * len(samples)
    source, output = tmp_path / "in.wav", tmp_path / "out.wav"
    rate = (8000, 16000, 24000, 44100)[case % 4]
    make_wav(source, samples, channels=channels, rate=rate)
    db = (-1.0, -3.0, -6.0, -12.0)[case % 4]
    enhance_wav(audio=source, output=output, highpass_hz=(0, 35, 65, 90, 150)[case % 5],
                peak_dbfs=db, noise_gate=(case % 2 == 0))
    with wave.open(str(output), "rb") as out:
        assert out.getnframes() == frames
        assert out.getframerate() == rate
        assert out.getnchannels() == channels
        assert out.getsampwidth() == 2
        decoded = array("h")
        decoded.frombytes(out.readframes(frames))
        if sys.byteorder != "little":
            decoded.byteswap()
        target_peak = 32767 * 10 ** (db / 20)
        assert max(map(abs, decoded), default=0) <= target_peak + 2
        assert len(decoded) == len(samples)


def test_bad_wav_input_fails(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not a WAV")
    with pytest.raises((ValueError, wave.Error, EOFError)):
        enhance_wav(audio=path, output=tmp_path / "out.wav")


@pytest.mark.parametrize("cutoff,peak", [(-1,-1),(201,-1),(65,-19),(65,0)])
def test_invalid_dsp_settings_rejected(tmp_path, cutoff, peak):
    with pytest.raises(ValueError):
        enhance_wav(audio=tmp_path/"none.wav",output=tmp_path/"o.wav",
                    highpass_hz=cutoff,peak_dbfs=peak)
