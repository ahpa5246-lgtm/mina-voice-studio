"""Check Whisper transcript exports with exact timing and no invented captions."""
import math
import pytest
from fastapi.testclient import TestClient
from studio import app as server
from studio.subtitles import subtitle_text

def test_srt_and_vtt_preserve_words_and_timestamp_precision():
    segments=[{"start":0.0,"end":1.25,"text":"مرحباً"},
              {"start":1.25,"end":3.8,"text":"يا عالم"}]
    srt=subtitle_text(segments,"srt")
    assert "00:00:00,000 --> 00:00:01,250" in srt
    assert "يا عالم" in srt
    vtt=subtitle_text(segments,"vtt")
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:01.250 --> 00:00:03.800" in vtt

@pytest.mark.parametrize("segments",[
    [{"start":-1,"end":1,"text":"word"}],
    [{"start":1,"end":1,"text":"word"}],
    [{"start":0,"end":float("nan"),"text":"word"}],
    [{"start":0,"end":1,"text":""}],
    [{"start":0,"end":1,"text":"x"*1001}],
])
def test_invalid_subtitle_timestamps_fail(segments):
    with pytest.raises(ValueError):
        subtitle_text(segments)

def test_transcript_download_only_for_completed_whisper_jobs(tmp_path,monkeypatch):
    monkeypatch.setattr(server,"DATA",tmp_path)
    with server.job_lock:
        server.jobs.clear()
        server.jobs["a"*32]={"engine":"transcribe","status":"completed",
            "transcript":{"text":"Hello","segments":[
                {"start":0,"end":1,"text":"Hello"}]}}
        server.jobs["b"*32]={"engine":"transcribe","status":"queued"}
    try:
        with TestClient(server.app) as c:
            good=c.get("/api/transcriptions/"+("a"*32)+"/srt")
            assert good.status_code==200
            assert "Hello" in good.text
            assert ".srt" in good.headers["content-disposition"]
            assert c.get("/api/transcriptions/"+("b"*32)+"/srt").status_code==404
            assert c.get("/api/transcriptions/"+("a"*32)+"/json").status_code==404
    finally:
        with server.job_lock:
            server.jobs.clear()
