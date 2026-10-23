"""Regression checks for public-facing GitHub onboarding documents."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_communicates_demo_and_production_limits():
    readme = text("README.md")
    assert readme.startswith("# Mina Voice Studio\n")
    for needle in ("Cartoon Cast", "Qwen3", "Chatterbox", "CONTRIBUTING.md",
                   "docs/INSTALL_AR.md", "127.0.0.1:7860",
                   "not safe to expose", "not been benchmarked on GPU"):
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
