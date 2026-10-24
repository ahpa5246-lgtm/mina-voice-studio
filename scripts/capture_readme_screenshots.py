"""Capture genuine, unedited browser screenshots of Mina's running UI.

No image mocks or generated 'screenshots': Chromium connects to the actual
FastAPI application with a temporary, empty local data directory.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "assets" / "screenshots"


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mina-doc-shots-") as tmp:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        env = dict(os.environ, MINA_DATA_DIR=tmp)
        for key in ("WHISPER_PYTHON", "QWEN_PYTHON", "CHATTERBOX_PYTHON", "APPLIO_ROOT",
                    "TTS_WEBUI_URL", "GPT_SOVITS_URL"):
            env.pop(key, None)
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "studio.app:app", "--host", "127.0.0.1",
             "--port", str(port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            for _ in range(150):
                if proc.poll() is not None:
                    raise RuntimeError(
                        "Studio failed to start: " + proc.stderr.read().decode()[-1000:])
                try:
                    with urlopen(url + "/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.15)
            else:
                raise RuntimeError("Studio did not pass the health check")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page(viewport={"width": 1440, "height": 900},
                                        device_scale_factor=1, reduced_motion="reduce")
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.locator("#lang").click()
                if page.locator("html").get_attribute("lang") != "en":
                    raise AssertionError("English UI did not activate")
                page.screenshot(path=str(IMAGES / "01-generate-speech.png"),
                                animations="disabled")
                page.locator('.nav[data-tab="cast"]').click()
                page.screenshot(path=str(IMAGES / "02-cartoon-cast.png"),
                                animations="disabled")
                page.locator("#episodeProjectTitle").scroll_into_view_if_needed()
                page.screenshot(path=str(IMAGES / "03-script-projects.png"),
                                animations="disabled")
                page.locator('.nav[data-tab="engines"]').click()
                page.locator("#acousticEvidence .engine-card").first.wait_for(timeout=15000)
                page.screenshot(path=str(IMAGES / "04-engines.png"),
                                animations="disabled")
                if errors:
                    raise AssertionError("Browser JavaScript errors: " + "; ".join(errors))
                browser.close()
            for path in sorted(IMAGES.glob("*.png")):
                print(path.relative_to(ROOT), path.stat().st_size, "bytes")
            assert len(list(IMAGES.glob("*.png"))) == 4
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
