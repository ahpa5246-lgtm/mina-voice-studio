"""Versioned, local-only cartoon episode script drafts.

Atomic JSON snapshots: no audio, external path, model weights or voice embeddings.
Optimistic version checks prevent tabs overwriting each other's dialogue.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
import time
from uuid import uuid4

from studio import cast

PROJECT_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_PROJECTS = 40
MAX_TITLE = 80


class ProjectConflict(ValueError):
    """Optimistic version mismatch or local capacity reached."""


def folder(root: Path) -> Path:
    out = root / "_projects"
    out.mkdir(parents=True, exist_ok=True)
    return out


def validate_title(title: object) -> str:
    if not isinstance(title, str):
        raise ValueError("Project title must be text.")
    name = title.strip()
    if not 1 <= len(name) <= MAX_TITLE or any(ord(char) < 32 for char in name):
        raise ValueError("Project title must have 1–80 printable characters.")
    return name


def list_projects(root: Path) -> list[dict]:
    result = []
    for file in folder(root).glob("*.json"):
        if not PROJECT_ID.fullmatch(file.stem):
            continue
        try:
            document = json.loads(file.read_text(encoding="utf-8"))
            if document["id"] != file.stem:
                continue
            title = validate_title(document["title"])
            if not isinstance(document["lines"], list):
                continue
            result.append({"id": file.stem, "title": title,
                           "version": document["version"],
                           "line_count": len(document["lines"]),
                           "updated": document["updated"]})
        except (OSError, KeyError, ValueError, TypeError):
            continue
    return sorted(result, key=lambda item: item["updated"], reverse=True)


def get_project(root: Path, identifier: str) -> dict:
    if not PROJECT_ID.fullmatch(identifier):
        raise FileNotFoundError("Unknown project.")
    file = folder(root) / (identifier + ".json")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("id") != identifier:
            raise ValueError("Project ID mismatch")
        validate_title(data["title"])
        if type(data["version"]) is not int or data["version"] < 1:
            raise ValueError("Invalid project version")
        if not isinstance(data["lines"], list) or len(data["lines"]) > cast.MAX_LINES:
            raise ValueError("Invalid project lines")
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FileNotFoundError("Project not found or unreadable.") from exc


def _write_atomic(file: Path, data: dict) -> None:
    handle, tmp = tempfile.mkstemp(prefix=".saving-", suffix=".tmp", dir=str(file.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, file)
    finally:
        Path(tmp).unlink(missing_ok=True)


def save_project(root: Path, *, title: str, lines: list[dict],
                 identifier: str | None = None,
                 expected_version: int | None = None) -> dict:
    title = validate_title(title)
    if identifier is None:
        if len(list_projects(root)) >= MAX_PROJECTS:
            raise ProjectConflict("Maximum of 40 saved projects reached.")
        if expected_version is not None:
            raise ProjectConflict("New projects cannot specify an old version.")
        identifier = uuid4().hex
        version = 1
        created = time.time()
    else:
        old = get_project(root, identifier)
        if type(expected_version) is not int or expected_version != old["version"]:
            raise ProjectConflict("Project changed in another tab. Reload before saving.")
        version = old["version"] + 1
        created = old["created"]
    # Validate against the canonical character profiles; never store injected models.
    checked = cast.validate_script(root, lines)
    serializable = [{"character_id": row["character"]["id"], "text": row["text"],
                     "delivery": row["delivery"], "pause_ms": row["pause_ms"]}
                    for row in checked]
    data = {"id": identifier, "version": version, "title": title,
            "created": created, "updated": time.time(), "lines": serializable}
    _write_atomic(folder(root) / (identifier + ".json"), data)
    return data


def delete_project(root: Path, identifier: str) -> None:
    get_project(root, identifier)
    (folder(root) / (identifier + ".json")).unlink()
