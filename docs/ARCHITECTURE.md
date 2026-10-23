# Architecture and scope

    Browser (Arabic RTL / English)
      |
    FastAPI: /api/health, /api/models, /api/speech, /api/convert, /api/jobs
      |
    Single-worker task executor to avoid simultaneous GPU-heavy jobs
      +-- Chatterbox worker, separate Python env -> real Multilingual V3 model
      +-- Applio worker, separate Python env -> real RVC conversion
      +-- TTS-WebUI, disabled until integrated and tested
      +-- GPT-SoVITS, disabled until integrated and tested

### Engineering decisions

1. Keep Torch/Transformers dependencies of independent engines isolated.
2. Report configuration readiness truthfully; detecting installed files does not prove speech synthesis quality.
3. Use no fabricated audio generation. API unit tests stub functions for orchestration coverage only.
4. Do not bundle model weights or represent upstream models as originally authored here.
5. Model IDs come from the configured Applio logs folder, not user-supplied arbitrary paths.
6. Run subprocesses with argument arrays, not shell interpolation, with a timeout and WAV existence checks.
7. Avoid exposing a public network server by default (bind to loopback). No authentication is implemented.
8. Uploaded files and outputs are stored in data/ until manually removed; jobs are in memory only.

### Known limitations

- Actual WAV synthesis quality and Iraqi dialect fidelity are untested.
- Chatterbox loads V3 model for every generation request: first-run downloads and startup costs are high.
- No persistent queue after application restart.
- Uploads validate filename extension and length but do not inspect audio file signatures or duration. Keep service local.
- Applio integration assumes the official core.py run_infer_script API; upstream changes may require adaptation.
- More advanced audio editing, real-time conversion, long-text segmentation, TTS-WebUI and GPT-SoVITS adapters are not built yet.

### Upstream sources (check license of code AND models before reuse)

- Chatterbox: https://github.com/resemble-ai/chatterbox
- Applio: https://github.com/IAHispano/Applio
- TTS-WebUI: https://github.com/rsxdalv/TTS-WebUI
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- XTTS-WebUI: https://github.com/daswer123/xtts-webui
