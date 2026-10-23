"""Optional LOCAL speech-engine HTTP connectors.

Never sends audio to a remote domain; endpoints restricted to loopback.
Provider APIs must run locally and may require provider-specific extensions.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


class ProviderError(RuntimeError):
    pass


def local_base_url(variable: str) -> str | None:
    raw = os.getenv(variable, "").strip().rstrip("/")
    if not raw:
        return None
    parsed = urlsplit(raw)
    if (parsed.scheme != "http" or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        return None
    try:
        if not parsed.port:
            return None
    except ValueError:
        return None
    if False:
        return None
    return raw


def available() -> list[dict]:
    return [
        {"id": "gpt-sovits", "title": "GPT-SoVITS API",
         "configured": local_base_url("GPT_SOVITS_URL") is not None,
         "note": "Configured URL only; health and voices not yet verified."},
        {"id": "tts-webui", "title": "TTS-WebUI OpenAI API extension",
         "configured": local_base_url("TTS_WEBUI_URL") is not None,
         "note": "Requires the separately enabled OpenAI speech API extension."},
    ]


def _post_json(url: str, payload: dict, output: Path) -> None:
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        method="POST")
    # ProxyHandler({}) is essential: private audio stays on loopback even
    # when the machine uses a proxy.
    class RejectRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ProviderError("Local provider attempted an HTTP redirect.")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), RejectRedirect())
    try:
        with opener.open(request, timeout=300) as response:
            if response.status != 200:
                raise ProviderError(f"Provider HTTP {response.status}")
            content_type = response.headers.get("Content-Type", "").lower()
            if "json" in content_type:
                raise ProviderError("Provider returned JSON, not audio; inspect its engine configuration.")
            limit = 100 * 1024 * 1024
            with output.open("wb") as sink:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    limit -= len(block)
                    if limit < 0:
                        raise ProviderError("Provider audio exceeds 100 MB")
                    sink.write(block)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        output.unlink(missing_ok=True)
        raise ProviderError(f"Local provider connection failed: {exc}") from exc


def synthesize_provider(*, provider: str, text: str, language: str, output: Path,
                        reference: Path | None = None, prompt_text: str = "",
                        voice: str = "default", model: str = "tts-1") -> None:
    if provider == "gpt-sovits":
        url = local_base_url("GPT_SOVITS_URL")
        if not url:
            raise ProviderError("Set GPT_SOVITS_URL to a local http://127.0.0.1:9880 endpoint")
        if language not in {"en", "zh", "ja", "ko"}:
            raise ProviderError("This adapter is limited to supported non-Arabic prompts; use Chatterbox for Arabic.")
        if not reference or not reference.exists() or not prompt_text.strip():
            raise ProviderError("GPT-SoVITS needs a local reference recording and its exact prompt transcript.")
        _post_json(url + "/tts", {
            "text": text, "text_lang": language, "ref_audio_path": str(reference.resolve()),
            "prompt_text": prompt_text, "prompt_lang": language,
            "text_split_method": "cut5", "media_type": "wav", "streaming_mode": False,
        }, output)
    elif provider == "tts-webui":
        url = local_base_url("TTS_WEBUI_URL")
        if not url:
            raise ProviderError("Set TTS_WEBUI_URL to the local speech API extension port, e.g. http://127.0.0.1:7778")
        if not model or not voice:
            raise ProviderError("Specify provider model and voice")
        _post_json(url + "/v1/audio/speech", {
            "model": model, "voice": voice, "input": text, "response_format": "wav",
        }, output)
    else:
        raise ProviderError("Unknown speech provider")
