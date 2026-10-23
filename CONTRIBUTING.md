# Contributing to Mina Voice Studio

Thanks for helping build an open-source voice acting workstation **for animation**. Please keep claims measurable and changes reproducible.

## What contributions are useful?

- Small, tested fixes in character casting, WAV/SRT exports, caption timing, browser accessibility or installer reliability.
- Verified upstream integration bugs, including Python/runtime versions and reproducible failure traces.
- Clear Windows, Linux/macOS and Arabic documentation.
- Genuine, rights-cleared synthetic demo clips **only if the license and speaker consent permit redistribution**.
- Benchmarks that distinguish a **real model run** from test doubles, with device, VRAM, latency and sample settings.

Before large feature work, [open an issue](https://github.com/ahpa5246-lgtm/mina-voice-studio/issues/new/choose) explaining user value and minimal acceptance tests.

## Local development

1. Fork the repository, clone your fork and create a descriptive branch.
2. Use **Python 3.11 or 3.12**. Create a virtual environment, then run:

   ```bash
   python -m pip install -r requirements-dev.txt
   python -m pytest -q
   ```

3. Check JS with `node --check studio/static/app.js`, plus any changed `studio/static/*.js` files.
4. For browser tests, install Playwright/Chromium and run `python -m pytest tests/test_browser.py -q`.
5. Open a pull request using the PR template, linking an issue when available. Explain your changes, exact commands run and **what you did not test**.

## Architecture / compatibility

- `studio/`: FastAPI app, adapters, voice libraries, cartoon cast and static UI.
- `scripts/`: isolated upstream workers, signal processing, benchmarks.
- `tests/`: Python integration, actual PCM16 processing and browser tests.
- `docs/`: setup, limitations, evaluations, legal/attribution guidance.
- `kaggle/`: user-runnable experiments, not evidence of completed GPU results.

Model weights are not bundled. **Do not** add huge pretrained files, captured private voices, proprietary datasets or undeclared network calls. Preserve upstream licenses and notices. The upstream model environments (Qwen, Chatterbox, Applio, Demucs) should stay isolated.

## Good pull-request checklist

- [ ] Clearly describe the problem, behavior before/after and user impact.
- [ ] Add or update tests, including negative/error-path cases.
- [ ] Use real upstream API contracts; no fabricated WAV files presented as neural output.
- [ ] Confirm Python tests and, when UI changes, browser/JS checks.
- [ ] Avoid logging speaker embeddings, reference audio or private paths.
- [ ] Document deployment limitations and external runtime dependencies.
- [ ] Mark simulated/mocked GPU checks and untested acoustic quality accurately.
- [ ] Ensure new code is compatible with Mina's MIT license and all upstream notices.

## Responsible voice tooling

Use authorized voices only. Never publish someone else's voice recording or likeness without consent. Public bug reports should contain sanitized logs and reproducible synthetic examples. The default local server lacks authentication and is **not suitable for exposing directly to the internet**.

## Maintainer expectations

Maintainers may request reproduction steps or test coverage before merging. Small, scoped PRs are easier to review. Issues proposing a feature are welcome even without working code. We do not promise a specific response time or request stars in exchange for support.
