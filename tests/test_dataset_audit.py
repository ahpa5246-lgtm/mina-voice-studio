import json
from pathlib import Path
import wave
from scripts.dataset_audit import audit_dataset


def wav(path: Path):
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        file.writeframes(b"\x01\x00" * 16000)


def test_rejects_missing_consent(tmp_path):
    wav(tmp_path / "sample.wav")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"audio":"sample.wav","text":"hello","language":"ar","speaker_id":"speaker","split":"train","consent":False}))
    result = audit_dataset(tmp_path, manifest)
    assert result["accepted"] == 0
    assert "consent" in result["issues"][0]["reason"].lower()


def test_accepts_valid_split_record_but_not_train_ready(tmp_path):
    wav(tmp_path / "sample.wav")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"audio":"sample.wav","text":"مرحبًا","language":"ar","speaker_id":"speaker","split":"train","consent":True}))
    result = audit_dataset(tmp_path, manifest)
    assert result["accepted"] == 1
    assert result["issues"] == []
    assert result["ready_for_training"] is False


def test_rejects_parent_directory_traversal(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"audio":"../secrets.wav","text":"hello","language":"en","speaker_id":"speaker","split":"train","consent":True}))
    assert "in-dataset" in audit_dataset(tmp_path, manifest)["issues"][0]["reason"]
