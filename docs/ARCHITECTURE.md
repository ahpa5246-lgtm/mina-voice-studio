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
- No persistent queue after application restart, and a maximum of 5 queued/running jobs.
- Uploads validate filename extension and length but do not inspect audio file signatures or duration. Keep service local.
- Applio integration assumes the official core.py run_infer_script API; upstream changes may require adaptation.
- More advanced audio editing, real-time conversion, long-text segmentation, TTS-WebUI and GPT-SoVITS adapters are not built yet.

### Upstream sources (check license of code AND models before reuse)

- Chatterbox: https://github.com/resemble-ai/chatterbox
- Applio: https://github.com/IAHispano/Applio
- TTS-WebUI: https://github.com/rsxdalv/TTS-WebUI
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- XTTS-WebUI: https://github.com/daswer123/xtts-webui

### Release 0.2 hardening
- A bounded five-job queue protects the single GPU worker.
- Additional jobs get HTTP 429; completed jobs older than 24h are cleaned during admission of new jobs, including old process directories.
- Refuse foreign-origin form posts and unrecognized hosts; these checks are not authentication.
- Uploaded signatures and WAV headers are validated, and output must be a readable WAV.
- Long text uses short pauses and 10ms fades; continuity across sections is not yet perceptually tested.

### Applio native backend integrations

- `studio.applio_advanced` handles argument validation and isolated upstream subprocesses for single and batch inference, model blending, pitch estimation, indexing, optional autotune, and native cleanup.
- `scripts/applio_native_worker.py` imports **original** Applio `core.py` at runtime. This is not an independently reverse-engineered reimplementation. Licensing/attribution to IAHispano is retained.
- `studio.applio_api` offers `/api/applio/batch`, `/api/applio/blend` and download. Filename upload paths are regenerated; model IDs resolve only to locally discovered Applio model files.
- Valid WAV output is required before batch ZIP success. Model blending requires a nonempty new checkpoint. Real GPU inference tests remain necessary for upstream compatibility.
- Applio upstream does include realtime code, but browser streaming, low latency and device routing have **not** been integrated into Mina and are explicitly disabled.
