# Mina Voice Studio

An Arabic-first, local-first open-source voice production workstation.

**Project status: early functional integration (not a finished ElevenLabs alternative).** The initial app provides a unified RTL/English interface, bounded queued jobs, a Chatterbox Multilingual V3 speech-generation adapter, and an Applio RVC conversion adapter. Both adapters require their original software/models installed separately; no model weights are redistributed.

## Features
- Arabic (RTL) and English interface, with voice-reference uploads and WAV playback/download.
- Long-form text chunking (up to 6000 characters per job), with a short pause between chunks; acoustic continuity has not been validated.\n- Text-to-speech with [Resemble AI Chatterbox](https://github.com/resemble-ai/chatterbox), including Arabic via the multilingual V3 checkpoint.
- File-based voice conversion with [Applio](https://github.com/IAHispano/Applio) and locally installed, user-authorized models.
- Isolated subprocess adapters so incompatible model dependencies do not share one Python environment.
- Explicit engine readiness checks, bounded sequential jobs, validated audio uploads, completed-job retention limits, and local-only default server.
- Audio generation is opt-in and restricted to voices you own or have permission to use.

## Quick start
Requires Python 3.11+ and separate engine environments.

```bash
git clone https://github.com/ahpa5246-lgtm/mina-voice-studio.git
cd mina-voice-studio
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn studio.app:app --host 127.0.0.1 --port 7860
```
Open http://127.0.0.1:7860 and inspect the **Engines** tab to see which backends need configuration. Follow [docs/INSTALL_AR.md](docs/INSTALL_AR.md) for engine setup.

> **Limitations:** This initial release is an integration MVP. It has not been benchmarked against ElevenLabs or evaluated on Iraqi Arabic pronunciation. No public cloud demo or permanent voice library has been deployed. GPT-SoVITS and TTS-WebUI are tracked as planned adapters, not presented as working integrations.

## Quality assurance\n- Test API, security boundaries, text segmentation, model catalog and error behavior with `pytest`.\n- `scripts/quality_report.py` calculates clipping, silence and RMS from local WAV outputs. These technical checks do not establish voice similarity, Arabic comprehension or human-level naturalness.\n- Genuine acoustic benchmarking and model fine-tuning require an appropriately licensed speech dataset and real GPU inference.\n\n## Upstream credits & licensing
Mina Voice Studio's original integration code is MIT-licensed. Chatterbox (MIT), Applio (MIT), and any other model/runtime remain independently installed and under their own licenses; check third-party model weights and conditions before distribution. This repository does not bundle or relicense upstream models.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Preparing an ethical fine-tuning dataset

`scripts/dataset_audit.py` checks that local WAV clips have transcripts, speaker IDs, train/validation/test split tags and an explicit consent declaration. See [evaluation protocol](docs/EVALUATION.md). **No new model weights have been trained yet.**
