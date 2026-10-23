# Mina Voice Studio

An Arabic-first, local-first open-source voice workstation. This is a development build, **not a validated replacement for ElevenLabs**. Model weights, training data, and other upstream software are installed separately.

## Tools and actual implementation status

| Workspace | Actual implementation | Dependencies / limitations |
| --- | --- | --- |
| Multilingual TTS & voice cloning | Chatterbox V3 speech worker, long-text chunking, optional voice reference | Separate runtime; no GPU quality benchmark |
| Voice conversion | Runs upstream Applio RVC with pitch shift, indexing, RMVPE/FCPE/CREPE, Autotune, and native Light/Speech cleanup | Installed model and separately installed Applio environment |
| Applio batch conversion | Converts 2–8 audio files via upstream batch inference, validates WAV outputs and downloads a ZIP | Installed Applio models and runtime |
| Applio model blender | Merges two compatible RVC checkpoints using Applio's own blender, refusing overwrites | Models with compatible architectures |
| Voice library | Save, list, preview, delete consented voice references | Stored locally in data/_voices |
| Cartoon cast studio | Persist character profiles and render a multi-speaker dialogue as episode WAV + per-line WAVs + SRT + ZIP | Uses existing installed Chatterbox and authorized voice references; 128 profiles / 48 lines per job |
| Audio enhancement | High-pass, peak normalization and optional gate on real PCM-16 samples | Conventional DSP, not neural denoising |
| Audio analysis | Clipping, silence, RMS, peak and duration | PCM-16 WAV only |
| Music/vocals separation | Run original Meta Demucs htdemucs two-stem CLI and export two verified WAV files in ZIP | Independent Demucs venv; weights/FFmpeg required |
| Speech transcription | Faster-Whisper worker for Arabic or English | Whisper installed separately and its weights downloaded |
| Script dubbing | Produce narration from your manually translated script | Chatterbox installed; no auto translation or lip-sync |
| TTS-WebUI API | Local OpenAI-compatible speech API connector | Needs separate API extension, model and voice selection |
| GPT-SoVITS API | Calls local /tts with voice recording and prompt transcript | Server can access reference path; Arabic not enabled in this adapter |
| Voice training | Audits consented local data, then launches Applio preprocess / extract / train and verifies checkpoint files | GPU and licensed dataset required; only command orchestration tested |
| Microphone capture | Records a five-second PCM WAV to feed clip conversion | Browser microphone; **not live GPU conversion** |
| Streaming voice changer | Not yet implemented | Persistent realtime transport/benchmark required |

## Installation

Python 3.11/3.12 is recommended. Create a virtual environment, install requirements.txt and launch the loopback server:

    git clone https://github.com/ahpa5246-lgtm/mina-voice-studio.git
    cd mina-voice-studio
    python -m venv .venv
    # Activate .venv for your OS
    python -m pip install -r requirements.txt
    python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860

Open http://127.0.0.1:7860. The interface starts without large models, but the relevant model workflows return clear errors until separately configured.

### Detailed documentation

- [Arabic setup and new tool guide](docs/EXTRA_TOOLS_AR.md)
- [Core setup instructions](docs/INSTALL_AR.md)
- [Architecture and limitations](docs/ARCHITECTURE.md)
- [Model training and acoustic evaluation protocol](docs/EVALUATION.md)

## Regression and browser tests

    python -m pip install -r requirements-dev.txt
    python -m pytest -q

CI runs **1,000 distinct deterministic PCM-16 WAV processing cases** plus API, permission and failure-path tests on Python 3.11 and 3.12. A separate headless Chromium job drives the real website and local server to test uploads, voice library operations and audio processing.

These are application and signal-processing tests, **not 1,000 model-inference runs**. The CI jobs do not download or fine-tune Chatterbox, Whisper, GPT-SoVITS or Applio models. For actual on-device model benchmarking, use scripts/smoke_audio.py and docs/EVALUATION.md.

## Privacy and licensing

- The server is restricted to loopback by default and is not safe to publish as a multi-user SaaS without authentication and additional abuse protection.
- Uploaded job recordings expire after 24 hours when a new job is admitted; saved voice references remain until you delete them.
- Only upload, convert or train on speakers whose permission you have.
- This repository's original code is MIT-licensed; installed upstream model licenses and terms still apply.
- Projects: [Chatterbox](https://github.com/resemble-ai/chatterbox), [Applio](https://github.com/IAHispano/Applio), [TTS-WebUI](https://github.com/rsxdalv/TTS-WebUI), [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS), [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper).

### Upstream Applio compatibility

This integration **calls the original Applio code** from a separate installation via `scripts/applio_native_worker.py` and does not redistribute upstream GPU weights. It uses Applio's native `core.run_infer_script`, `core.run_batch_infer_script`, and `core.run_model_blender_script`. On-demand Light cleanup can require FFmpeg; Speech cleanup may download DeepFilterNet components on the user machine. DeepFilterNet is not the same as music/vocal source separation. Live voice streaming and vocal/instrument splitting are **not integrated** into Mina yet. Until tested against real RVC weights, call status configured, not audio-verified.

## Upstream-derived engine integration (Oct 2026)

Mina invokes independently installed **MIT-licensed** upstream model runtimes rather than copying their entire incompatible Python environments. The Chatterbox adapter now accepts Multilingual V3 (23 languages), Turbo (English) and Nano (English) through the original Resemble AI API; Turbo/Nano require an authorized reference clip. A local-only **stdio process** caches exactly one Chatterbox model at a time and is explicitly releasable from the Engines screen. No TCP inference daemon or third-party model weights are distributed.

Faster-Whisper transcription results can be exported as SRT or WebVTT using the actual recognized segment timestamps. This is subtitle *export*, **not** automatic dubbing/lip synchronization. GPT-SoVITS and TTS-WebUI local API adapters are available in the additional providers screen, but do not count as verified until real audio has been produced.

To run the real hardware tests on a configured machine:

```powershell
python scripts/smoke_audio.py --operation speech --chatterbox-model multilingual-v3 --language ar --text "مرحبا بك" --output data/ar.wav
python scripts/smoke_audio.py --operation speech --chatterbox-model turbo --language en --reference C:\path\to\authorized-voice.wav --text "Welcome!" --output data/turbo.wav
```

CI covers the private stdio protocol, security gates, actual WAV signal processing, subtitle timestamps and browser wiring. **CI does not download model weights or establish acoustic fidelity.** Compare naturalness and accent only after listening to real generated recordings. See [upstream integration notes](docs/UPSTREAM_INTEGRATION.md).

## Demucs source separation

The **Vocal separation** workspace invokes the original [MIT-licensed Meta Demucs](https://github.com/facebookresearch/demucs) command in a dedicated Python environment. The optional upstream repository is archived, so future compatibility is not guaranteed. Install it yourself before using this feature. The app validates both `vocals.wav` and `instrumental.wav` rather than inventing separated audio, and fails transparently without model weights or an installed runtime. No pretrained model files are included.

```powershell
py -3.11 -m venv .venv-demucs
.\.venv-demucs\Scripts\python.exe -m pip install demucs
$env:DEMUCS_PYTHON = (Resolve-Path '.venv-demucs\Scripts\python.exe').Path
```

You will also need the multimedia decoder dependencies supported by Demucs, normally FFmpeg. Model weights can download on first use. This is an isolated heavy audio job, not a streaming/live separation feature.

## Cartoon Voice Cast Studio — real dialogue renders

The **Cartoon Cast** tab lets you create persistent character voice profiles, link existing consented recordings from the **Voice Library**, set a Chatterbox model/language and expressiveness/guidance values, enter multi-speaker dialogue lines, and select approximate delivery directions. It renders each line using the genuine installed model, concatenates PCM16 WAV clips, and exports: `episode.wav`, `dialogue.srt`, `manifest.json`, and one individual WAV file per line, wrapped in a ZIP. Failed lines fail the entire job.

Distinct names do **not** create distinct vocal timbres. Different authorized reference samples (or suitable separately trained RVC models used in a later conversion step) are required for distinguishable speaker identities. No text-prompt speaker design akin to ElevenLabs Voice Design is implemented. No guarantee of Iraqi-accent accuracy, animated emotion, lip sync or actor-quality performance.

**Current local capacity:** 128 saved voice recordings, 128 character profiles, up to 48 dialogue lines and 6,000 total characters per episode job. These are explicit software limits, not an unlimited voice-generation claim. Voice reference audio and character profiles persist until deleted; generated episode jobs are temporary and cleared through normal local retention.

To test Chatterbox with actual authorized voice files, install the separate Chatterbox environment as in the [Arabic setup guide](docs/INSTALL_AR.md) and run `scripts/smoke_audio.py`. No GPU acoustic-quality claim is made by the HTTP/browser test suite.

## Qwen3 Voice Design, reusable cartoon identities and acting controls

Mina now integrates the real **Apache-2.0 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)** via a separate Python process. Its **VoiceDesign 1.7B** can synthesize an entirely new voice seed from a written English description (no speaker recording). The seed audio and exact spoken transcript are stored in Mina's reference library. Assign the seed to a recurring **Qwen Clone** character in Cartoon Cast: **Base 1.7B** reuses the same reference audio/transcript and a cached clone prompt across dialogue lines. This is the technically correct route to keeping an invented character timbre consistent.

Per-line acting direction ("sarcastic", "angry", "sad", "crying", etc.) is wired through **Qwen CustomVoice 1.7B**, using its nine preset speakers and official `instruct` argument. **The Base clone checkpoint does not support per-line acting instructions**. Its generated speech remains governed by the seed and text. Character differentiation/expressiveness are not guaranteed.

Official Qwen3 12Hz voice models support ten languages: English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish and Italian. **No Arabic**; use Chatterbox Multilingual V3 for Arabic cartoons. No 0.6B VoiceDesign is claimed.

### Installation (local Windows or Kaggle GPU)

Qwen is optional, and must **not** be installed into the existing Chatterbox/Applio environment:

```powershell
py -3.12 -m venv .venv-qwen
.\.venv-qwen\Scripts\python.exe -m pip install qwen-tts soundfile
$env:QWEN_PYTHON = (Resolve-Path '.venv-qwen\Scripts\python.exe').Path
python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
```

First inference downloads public model weights (multiple GB) unless already cached. Check model cards and available VRAM; the process caches one active Qwen checkpoint, releasing it when switching model families. This avoids loading design, clone and CustomVoice weights together, but still does **not** prove GPU compatibility on your PC.

### Run the first GPU benchmark on Kaggle

Import the versioned notebook [kaggle/cartoon_voices_qwen3.ipynb](kaggle/cartoon_voices_qwen3.ipynb) into Kaggle Notebooks, enable an available GPU, and enable internet if permitted for downloading public weights. Execute all cells. It builds two **entirely synthetic voices**, generates three repeated lines from each with Base clone, generates three acted lines with CustomVoice, and compares within-speaker versus between-speaker Resemblyzer embedding cosine similarity. It exports **actual** WAV files and metrics JSON. These operations were **not executed** in GitHub CI or this environment. The notebook is a reproducible experiment, not completed training or proof of commercial parity.

For real episodes created inside Mina, optionally install `resemblyzer` and run `python scripts/voice_consistency.py path/to/episode.zip`. Embedding similarity is a proxy; use a blinded listening test across multiple voices/scenes and evaluate naturalness, drift, failures, GPU memory and real-time factor. Do not claim ElevenLabs parity based on similarity numbers alone.

See the [Arabic Qwen + Kaggle guide](docs/QWEN_KAGGLE_AR.md).

### Optional in-app episode voice-consistency report

After an actual episode has finished rendering, the Cartoon Cast page displays **Measure character voice consistency**. Install `resemblyzer` in Mina's own **web-server** Python environment to enable it. The report compares GE2E speaker embeddings from real generated lines, counts within/between-character pairs and exposes mean cosine and minimum pair similarity, with **no pass/fail threshold**. Short recordings or incompatible audio correctly fail rather than producing fake values. Model weights will be downloaded on first use when the optional package supports it. No score is presented as proof of voice authenticity, especially for highly stylized characters or Arabic.
