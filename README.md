# Mina Voice Studio

**Open-source AI voice acting studio for animation and cartoons.**

Create character voices, write multi-speaker dialogue, render line-by-line WAV audio, and export your cartoon's voice track and timed subtitles. **Local-first · Arabic/English interface · MIT-licensed application code.**

[![Python tests](https://github.com/ahpa5246-lgtm/mina-voice-studio/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ahpa5246-lgtm/mina-voice-studio/actions/workflows/tests.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Alpha](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/ahpa5246-lgtm/mina-voice-studio/releases)
[![Python 3.11–3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-informational.svg)](https://www.python.org/)

> **Alpha / developer preview:** The UI and deterministic audio/HTTP flows have automated tests; **neural model output quality has not been benchmarked on GPU**. Speech engines and checkpoints are **not included**. This is not an ElevenLabs replacement claim. The local app is **not safe to expose as a public multi-user service**.

**[Quick start](#quick-start--windows-macos-linux) · [Features](#what-can-it-do) · [Cartoon workflow](#make-a-short-cartoon-scene) · [Arabic guide](docs/INSTALL_AR.md) · [Contribute](CONTRIBUTING.md) · [Issues](https://github.com/ahpa5246-lgtm/mina-voice-studio/issues) · [Releases](https://github.com/ahpa5246-lgtm/mina-voice-studio/releases)**

## In 30 seconds

Mina manages the *audio-production side* of animation. You choose character voices and deliver dialogue; the app invokes the installed upstream synthesizer, then prepares editable dialogue clips, a merged track, and subtitles. **It is not a video editor, lip-sync generator, or hosted GPU demo.**

```text
Script + characters + licensed voice references
  ↓
VoiceDesign (Qwen, English) / Chatterbox (including Arabic)
  ↓
Cartoon Cast → generated line WAVs → episode WAV + SRT + manifest
  ↓
Download ZIP → edit and animate in your preferred video editor
```

### What can it do?

| Workspace | Implemented behavior | Readiness |
| --- | --- | --- |
| **Character casting** | Up to 128 profiles; voice references, per-line speakers, script timing, exported WAV/SRT/ZIP | App/API tested; audio models external |
| **Voice design** | Qwen3 VoiceDesign 1.7B: new synthetic speaker reference from descriptive text | Optional checkpoint; official model excludes Arabic |
| **Consistent characters** | Qwen3 Base voice clone reuses a generated or consented seed/transcript | Requires real-model listening test |
| **Acting directions** | Qwen3 CustomVoice preset voices accept sarcasm/anger/sadness/crying instructions | Per-line controls apply to *preset* voices, **not Qwen Base clone** |
| **Multilingual speech** | Chatterbox Multilingual V3 (includes Arabic); Turbo and Nano for English | Separate Chatterbox installation |
| **Voice conversion / training** | Original Applio/RVC single + batch conversion, model blending, training orchestrator | Separate Applio install, models, licensed recordings |
| **Voice library** | Save, preview and reuse local authorized reference clips | Local/consent gated |
| **Transcription & subtitles** | Faster-Whisper; real-timestamp SRT and WebVTT exports | Whisper checkpoint installed separately |
| **Audio cleanup / diagnostics** | High-pass filtering, normalization, gate, clipping/peak/silence measurements | Deterministic PCM16 signal-processing tests |
| **Stem splitting** | Demucs real vocal/instrumental CLI adapter + verified WAV ZIP | Separate Demucs install/weights |
| **Manual voiceover** | Generate voiceover for a supplied translation | Not auto-translation or automatic dubbing |
| **Other providers** | Optional local TTS-WebUI and GPT-SoVITS HTTP adapters | Requires their locally running APIs |
| **Speaker stability report** | Optional Resemblyzer within/between-character cosine comparisons | Approximate; never an objective voice-quality pass |
| **Kaggle benchmark** | Notebook to design two English synthetic voices, clone lines, and inspect similarity | **Notebook supplied; not run on Kaggle by maintainers** |

**Not implemented:** low-latency live voice changing, automatic lip-sync, multitrack video timeline, an online unrestricted GPU demo, accounts or production multi-user authentication.

## Quick start — Windows, macOS, Linux

Requires Python 3.11 or 3.12 and Git. The basic app **starts without a GPU** but cannot synthesize speech without separate model environments and downloaded weights.

```bash
git clone https://github.com/ahpa5246-lgtm/mina-voice-studio.git
cd mina-voice-studio
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
```

Open **http://127.0.0.1:7860**.

Windows PowerShell alternative: run `.\start.ps1` in the repository root (requires Python 3.11). Linux/macOS: `bash start.sh`. Use [Arabic engine-by-engine setup](docs/INSTALL_AR.md) to enable actual voice generation. Each AI engine has an intentionally separate Python environment to avoid dependency conflicts.

### Make a short cartoon scene

1. **Choose characters.** Start with **Cartoon Cast**. For an English synthetic character, use Qwen VoiceDesign to render a new seed; save its WAV and exact transcript. For Arabic, choose Chatterbox with an authorized reference.
2. **Save the cast.** Link the reference voice to each character. Select **Qwen Clone** to keep an invented English timbre or **Qwen CustomVoice** for preset-speaker acting instructions.
3. **Write the dialogue.** Assign a speaker, text, approximate delivery and pause to each line. One render handles **up to 48 lines / 6,000 characters**.
4. **Render and listen.** After successful upstream inference, export `episode.wav`, each `lines/line-XXX.wav`, `dialogue.srt` and `manifest.json` in a ZIP. Use the optional speaker similarity report, but validate by listening.
5. **Animate.** Arrange the individual WAV files, visuals, sound effects and music in your video editor. Mina does not yet render animation or perform lip-sync.

## First GPU evaluation: Kaggle

Open [the Qwen3 cartoon-voices notebook](kaggle/cartoon_voices_qwen3.ipynb) and follow the [Arabic Kaggle instructions](docs/QWEN_KAGGLE_AR.md). Enable a Kaggle GPU and network access if available. It tests **English** voice design, multi-line clone reuse, acted preset voices and embedding similarity. Kaggle quotas and downloads vary. **No GPU benchmark results are represented as completed.**

## Testing and project transparency

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs Python 3.11, Python 3.12 and headless Chromium. It tests actual app routing, file processing and controlled upstream-engine adapters, but **mocks neural audio inference**, so it does **not** prove convincing character acting, voice similarity, Iraqi accent or model VRAM performance.

- [Architecture](docs/ARCHITECTURE.md) · [Voice quality evaluation](docs/EVALUATION.md)
- [Qwen/Kaggle instructions (Arabic)](docs/QWEN_KAGGLE_AR.md) · [Applio attribution](docs/APPLIO_ATTRIBUTION.md) · [Upstream adapters](docs/UPSTREAM_INTEGRATION.md)
- [Release notes](docs/releases/v0.1.0-alpha.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## Contributing and community

Bug reports, reproducible model-compatibility findings, accessibility improvements, tests, audio-editor contributions and clear documentation are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md) or open a [bug report / feature request](https://github.com/ahpa5246-lgtm/mina-voice-studio/issues/new/choose). Please do not upload private recordings, unlicensed model weights, API tokens or biometric speaker data into public issues.

**Licensing:** Mina's code is [MIT](LICENSE). It integrates, but does not redistribute, separately licensed upstream code/models: [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [Chatterbox](https://github.com/resemble-ai/chatterbox), [Applio](https://github.com/IAHispano/Applio), [Demucs](https://github.com/facebookresearch/demucs), [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper). Check each checkpoint's terms and obtain speaker consent before cloning or converting any voice.

*Built to help independent animators tell stories with reproducible, locally controlled voice tools.*
