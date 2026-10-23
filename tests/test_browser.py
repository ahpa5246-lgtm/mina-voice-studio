"""Real headless Chromium checks: browser forms, HTTP, and actual PCM processing.

Run with: pip install playwright && python -m playwright install chromium
then: pytest tests/test_browser.py -q
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import wave

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x12\x00\xed" * 2400)
    return output.getvalue()


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("mina-site")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = dict(os.environ, MINA_DATA_DIR=str(root))
    for variable in ("WHISPER_PYTHON", "CHATTERBOX_PYTHON", "GPT_SOVITS_URL", "TTS_WEBUI_URL", "APPLIO_ROOT"):
        env.pop(variable, None)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "studio.app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError("Local server failed to start: " + process.stderr.read().decode()[-1800:])
            try:
                with urlopen(url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(.1)
        else:
            raise RuntimeError("Local server did not respond to HTTP health checks")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        instance = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        yield instance
        instance.close()


@pytest.fixture
def page(browser, site):
    current = browser.new_page(viewport={"width": 1365, "height": 900})
    errors = []
    current.on("pageerror", lambda exception: errors.append(str(exception)))
    current.goto(site, wait_until="networkidle")
    yield current, errors
    current.close()


def test_ui_loads_all_nine_real_workspaces(page):
    current, errors = page
    assert current.title() == "Mina Voice Studio"
    assert current.locator(".nav").count() == 9
    assert current.locator(".tab").count() == 9
    assert current.locator("#speech").is_visible()
    assert not errors, errors


def test_language_toggle_applies_to_live_dom(page):
    current, errors = page
    current.locator("#lang").click()
    assert current.locator("html").get_attribute("lang") == "en"
    assert current.locator("html").get_attribute("dir") == "ltr"
    assert "Generate speech" in current.locator('.nav[data-tab="speech"]').inner_text()
    assert not errors, errors


def test_voice_library_save_play_and_delete(page):
    current, errors = page
    current.locator('.nav[data-tab="library"]').click()
    current.locator("#voiceName").fill("Consented reference")
    current.locator("#voiceFile").set_input_files({
        "name": "voice.wav", "mimeType": "audio/wav", "buffer": wav_bytes()
    })
    current.locator('#voiceForm input[name="consent"]').check()
    current.locator('#voiceForm button[type="submit"]').click()
    current.locator(".voice-item").first.wait_for(timeout=15000)
    assert current.locator(".voice-item audio").first.get_attribute("src").startswith("/api/voices/")
    current.on("dialog", lambda dialog: dialog.accept())
    current.locator(".voice-item button").first.click()
    current.locator(".voice-item").first.wait_for(state="detached", timeout=15000)
    assert not errors, errors


def test_wav_analyzer_runs_end_to_end(page):
    current, errors = page
    current.locator('.nav[data-tab="cleanup"]').click()
    current.locator("#qualityAudio").set_input_files({
        "name": "audio.wav", "mimeType": "audio/wav", "buffer": wav_bytes()
    })
    current.locator('#qualityForm button[type="submit"]').click()
    current.wait_for_function("""() => document.querySelector('#qualityResult').textContent.includes('"sample_rate": 16000')""", timeout=15000)
    assert "clipped_percent" in current.locator("#qualityResult").inner_text()
    assert not errors, errors


def test_wav_cleanup_generates_playable_file(page):
    current, errors = page
    current.locator('.nav[data-tab="cleanup"]').click()
    current.locator("#enhanceAudio").set_input_files({
        "name": "audio.wav", "mimeType": "audio/wav", "buffer": wav_bytes()
    })
    current.locator('#enhanceForm button[type="submit"]').click()
    current.locator("#enhanceAudioResult").wait_for(state="visible", timeout=20000)
    src = current.locator("#enhanceAudioResult").get_attribute("src")
    assert src.startswith("/api/jobs/") and src.endswith("/audio")
    assert current.locator("#enhanceDownload").is_visible()
    assert not errors, errors


def test_missing_whisper_engine_reports_error_not_faked_transcript(page):
    current, errors = page
    current.locator('.nav[data-tab="transcription"]').click()
    current.locator("#transcribeAudio").set_input_files({
        "name": "audio.wav", "mimeType": "audio/wav", "buffer": wav_bytes()
    })
    current.locator('#transcribeForm button[type="submit"]').click()
    current.wait_for_function("""() => document.querySelector('#transcribeStatus').textContent.includes('503') || document.querySelector('#transcribeStatus').textContent.includes('faster-whisper')""", timeout=15000)
    assert current.locator("#transcriptResult").input_value() == ""
    assert current.locator("#transcribeAudio").is_visible()
    assert not errors, errors


def test_missing_tts_engine_reports_dependency_error(page):
    current, errors = page
    current.locator('.nav[data-tab="dubbing"]').click()
    current.locator("#dubText").fill("مرحبا بالعالم")
    current.locator('#dubForm input[name="consent"]').check()
    current.locator('#dubForm button[type="submit"]').click()
    current.wait_for_function("""() => document.querySelector('#dubStatus').textContent.includes('Chatterbox')""", timeout=15000)
    assert current.locator("#dubAudio").is_hidden()
    assert not errors, errors


def test_responsive_mobile_navigation_without_page_overflow(browser, site):
    page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    page.goto(site, wait_until="networkidle")
    assert page.locator("#speechForm").is_visible()
    page.locator('.nav[data-tab="library"]').click()
    assert page.locator("#voiceForm").is_visible()
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 2")
    assert not errors, errors
    page.close()


def test_training_launcher_shows_missing_setup_instead_of_fake_success(page):
    current, errors = page
    current.locator('.nav[data-tab="training"]').click()
    current.locator("#trainName").fill("Mina_Model_123")
    current.locator('#trainingForm input[name="consent"]').check()
    current.locator('#trainingForm input[name="acknowledge"]').check()
    current.locator('#trainingForm button[type="submit"]').click()
    current.wait_for_function("""() => {
      const msg = document.querySelector('#trainStatus').textContent;
      return msg.includes('503') || msg.includes('APPLIO_TRAIN_DATA') || msg.includes('Install Applio');
    }""", timeout=15000)
    assert not errors, errors
