# External upstream reuse and verification

**Policy:** Borrow the original upstream implementation behind adapters; do not blindly vendor three full incompatible environments. Comply with the MIT license and retain attribution. Models/weights and datasets may have independent license and consent requirements.

| Upstream | What Mina actually uses | Missing/untested |
| --- | --- | --- |
| [Chatterbox / Resemble AI](https://github.com/resemble-ai/chatterbox) | `ChatterboxMultilingualTTS` V3 and `ChatterboxTurboTTS` Turbo/Nano directly; a stdio model host caches one active model | No benchmark of naturalness, accuracy, VRAM, long-form drift, GPU compatibility |
| [Applio / IAHispano](https://github.com/IAHispano/Applio) | Original RVC single/batch inference, model blender, and training CLI through an isolated installation | No on-device RVC quality test; live streaming not connected |
| [TTS-WebUI / rsxdalv](https://github.com/rsxdalv/TTS-WebUI) | Optional loopback OpenAI-compatible speech API extension adapter | Not the entire engine/extensions catalog; endpoint must be installed and tested |
| [GPT-SoVITS / RVC-Boss](https://github.com/RVC-Boss/GPT-SoVITS) | Optional loopback `api_v2.py` speech endpoint | Other model versions/languages may need adjustments |
| [faster-whisper / SYSTRAN](https://github.com/SYSTRAN/faster-whisper) | Real timestamped ASR segment worker; SRT and WebVTT exports | Whisper inference and transcription accuracy not measured in hosted CI |

**Real model quality gate:** Test fixed, permissioned Arabic, Iraqi dialect and English samples using the genuine model weights. Capture speaker similarity, WER/CER, latency, VRAM, hallucination and failed requests. Use blinded listening before claiming superiority.

**Model-cache privacy:** Chatterbox resets default conditionals after any reference-conditioned speech. Only one model is held warm; queued tasks are serialized. Model unload is rejected while synthesis is active. No public GPU TCP endpoint exists. The app still has no user authentication and must not be exposed as an untrusted multi-user service.

**CI scope:** Python integration/unit tests, actual deterministic PCM audio processing, browser form traversal, and stdio worker health pings. A successful ping does not prove that a model is installed or generates natural audio.

### Meta Demucs via TTS-WebUI's source-separation ecosystem

Use original [facebookresearch/demucs](https://github.com/facebookresearch/demucs) (MIT copyright Meta Platforms, Inc.) through `python -m demucs --two-stems vocals -n htdemucs` in an isolated Python venv. Similar source separation is available in TTS-WebUI extensions. Mina's adapter verifies two actual WAV outputs and packages ZIP only on success. CI mocks the external CLI but operates on actual WAV fixtures, so it does **not** demonstrate separation quality, GPU inference, or compatibility with every Demucs dependency revision. The original Demucs GitHub repository is archived.

## High-quality mixed-model episode assembly

Voice episodes use the independent [Python-SoXR](https://github.com/dofuuz/python-soxr) implementation of libsoxr (`soxr.resample(..., quality="HQ")`) to convert PCM16 audio between engine sample rates. The binding and bundled libsoxr are LGPL-2.1-or-later, not MIT; the package is an external runtime dependency, not a copy of its implementation. NumPy handles mono/stereo PCM16 channel conversion and safe clipping. Unit tests verify sample rates and nondestructive per-line regeneration; no perceptual human-listening claim is implied.
