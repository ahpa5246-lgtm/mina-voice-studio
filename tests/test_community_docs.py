"""Regression checks for public-facing GitHub onboarding documents."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_communicates_demo_and_production_limits():
    readme = text("README.md")
    assert "# Mina Voice Studio\n" in readme
    for needle in ("Cartoon Cast", "Qwen3", "Chatterbox", "CONTRIBUTING.md",
                   "docs/INSTALL_AR.md", "127.0.0.1:7860",
                   "not a hosted online demo", "Kaggle Tesla T4"):
        assert needle.lower() in readme.lower(), needle
    assert readme.count(chr(96) * 3) % 2 == 0
    assert "\\" + chr(96) not in readme


def test_issue_forms_are_parseable_and_have_required_fields():
    for name in ("bug_report", "feature_request"):
        obj = yaml.safe_load(text(f".github/ISSUE_TEMPLATE/{name}.yml"))
        assert obj["name"]
        assert obj["description"]
        assert obj["body"]
        assert any(item.get("validations", {}).get("required")
                   for item in obj["body"])
    config = yaml.safe_load(text(".github/ISSUE_TEMPLATE/config.yml"))
    assert config["blank_issues_enabled"] is False
    assert any("SECURITY.md" in link["url"] for link in config["contact_links"])


def test_release_is_only_published_after_trusted_main_ci():
    workflow = yaml.safe_load(text(".github/workflows/release-alpha.yml"))
    assert workflow.get("on", workflow.get(True))["workflow_run"]["types"] == ["completed"]
    job = workflow["jobs"]["release"]
    guard = job["if"]
    for phrase in ("workflow_run.conclusion", "workflow_run.event",
                   "workflow_run.head_branch", "main"):
        assert phrase in guard
    command = job["steps"][1]["run"]
    assert "TESTED_SHA" in command
    assert "v0.1.0-alpha" in command
    assert "--prerelease" in command
    assert "--notes-file" in command
    assert "--target" in command
    assert text("docs/releases/v0.1.0-alpha.md").startswith("# Mina Voice Studio v0.1.0-alpha")


def test_contributing_and_security_docs_exist():
    assert "python -m pytest" in text("CONTRIBUTING.md")
    assert "not suitable for exposing" in text("CONTRIBUTING.md")
    assert "Do not expose" in text("SECURITY.md")
    assert "administration" in text("docs/REPOSITORY_METADATA.md")


def test_kaggle_workflow_accepts_both_secret_names():
    workflow = text(".github/workflows/kaggle-voice-benchmark.yml")
    assert "secrets.KAGGLE_API_TOKEN || secrets.KAGGLE" in workflow
    assert "--no-run" in workflow
    assert "KAGGLE_API_TOKEN: " in workflow
    docs = text("docs/REAL_AUDIO_TEST_AR.md")
    assert "KAGGLE_API_TOKEN" in docs and "`KAGGLE`" in docs


def test_one_time_kaggle_activation_yaml_is_parseable_and_guarded():
    workflow = yaml.safe_load(text(".github/workflows/kaggle-voice-benchmark.yml"))
    triggers = workflow.get("on", workflow.get(True))
    assert "main" in triggers["push"]["branches"]
    assert ".github/workflows/kaggle-voice-benchmark.yml" in triggers["push"]["paths"]
    assert "workflow_dispatch" in triggers
    guard = workflow["jobs"]["kaggle"]["if"]
    assert "startsWith" in guard and "workflow_dispatch" in guard
    assert "ci: launch first private Kaggle voice benchmark" in guard
    env = workflow["jobs"]["kaggle"]["env"]
    assert "minahussain111" in env["KAGGLE_USERNAME_INPUT"]
    assert "'true'" in env["RUN_GPU_INPUT"]


def test_kaggle_asr_bypasses_incompatible_pyav_and_saves_partial_audio():
    import ast
    import json
    notebook = json.loads(text("kaggle/cartoon_voices_qwen3.ipynb"))
    blocks = [item["source"] for item in notebook["cells"] if item["cell_type"] == "code"]
    source = ["".join(block) for block in blocks]
    for block in source:
        # Notebook cells must be parseable after stripping pip shell magic.
        assert ast.parse("\n".join(line for line in block.splitlines()
                                   if not line.startswith("!")))
    assert any("soxr" in block and "pip -q install" in block for block in source)
    assert any("preliminary metrics" in block and "zipfile.ZipFile" in block for block in source)
    whisper_cell = next(block for block in source if "asr_model.transcribe(" in block)
    assert "sf.read" in whisper_cell
    assert "soxr.resample" in whisper_cell
    assert "asr_model.transcribe(audio16" in whisper_cell
    assert "asr_model.transcribe(str(path)" not in whisper_cell


def test_kaggle_retry_requires_specific_activation_commit_title():
    import yaml
    workflow = yaml.safe_load(text(".github/workflows/kaggle-voice-benchmark.yml"))
    triggers = workflow.get("on", workflow.get(True))
    assert "kaggle/cartoon_voices_qwen3.ipynb" in triggers["push"]["paths"]
    guard = workflow["jobs"]["kaggle"]["if"]
    assert "ci: rerun Kaggle ASR fix after real voice generation" in guard
    assert "workflow_dispatch" in guard

def test_readme_uses_genuine_checked_in_browser_images():
    import re
    import struct
    import xml.etree.ElementTree as ET
    readme = text("README.md")
    images = re.findall(r"!\[[^]]*\]\((docs/assets/[^)]+)\)", readme)
    assert "docs/assets/hero.svg" in images
    assert "docs/assets/workflow.svg" in images
    screenshots = [path for path in images if path.endswith(".png")]
    assert len(screenshots) == 4
    assert len(set(screenshots)) == len(screenshots)
    for image in images:
        path = ROOT / image
        assert path.is_file() and path.stat().st_size > 100, image
        if path.suffix == ".svg":
            assert ET.parse(path).getroot().tag.endswith("svg")
        else:
            png = path.read_bytes()
            assert png.startswith(bytes((137, 80, 78, 71, 13, 10, 26, 10)))
            width, height = struct.unpack(">II", png[16:24])
            assert (width, height) == (1440, 900)
    assert "Playwright" in readme and "captured from" in readme.lower()


def test_readme_has_real_install_command_and_honest_upstream_limits():
    readme = text("README.md")
    for needle in ("git clone https://github.com/ahpa5246-lgtm/mina-voice-studio.git",
                   ".\\\\start.ps1", "bash start.sh", "http://127.0.0.1:7860",
                   "model weights are separate downloads", "Qwen3-TTS",
                   "Chatterbox", "Applio", "Faster-Whisper", "SoXR",
                   "Local app", "MIT", "Kaggle Tesla T4"):
        assert needle.lower() in readme.lower(), needle
