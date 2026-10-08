"""Dev-only: keep every scored recording, to build an evaluation set from real takes.

On only when SPEECH_DEBUG_DUMP_DIR is set, and never inside a container: recordings are
learner voices, and a production image must not be able to keep them, whatever its
environment says. Each request gets its own directory:

    <dir>/<UTC time>-<8 hex>/audio<ext>      the bytes as received
    <dir>/<UTC time>-<8 hex>/request.json    referenceText, filename, content type
    <dir>/<UTC time>-<8 hex>/response.json   status and the body sent back (score or error)
"""

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONTAINER_MARKERS = (Path("/.dockerenv"), Path("/run/.containerenv"))


def in_container(markers: tuple[Path, ...] = CONTAINER_MARKERS) -> bool:
    # podman and systemd-nspawn set lowercase `container`; Docker leaves /.dockerenv.
    return bool(os.environ.get("container")) or any(m.exists() for m in markers)  # noqa: SIM112


def dump_dir(configured: Path | None, markers: tuple[Path, ...] = CONTAINER_MARKERS) -> Path | None:
    """The directory to dump into, or None. Refuses (and says so) inside a container."""
    if configured is None:
        return None
    if in_container(markers):
        logger.error("SPEECH_DEBUG_DUMP_DIR is set inside a container; audio is NOT dumped")
        return None
    logger.warning("dev audio dump ON: every scored recording is kept in %s", configured)
    return configured


def save(
    root: Path,
    audio: bytes,
    filename: str | None,
    content_type: str | None,
    reference_text: str,
    status: int,
    body: Any,
) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    target = root / f"{stamp}-{uuid.uuid4().hex[:8]}"
    target.mkdir(parents=True)
    (target / f"audio{Path(filename or '').suffix[:8]}").write_bytes(audio)
    request = {"referenceText": reference_text, "filename": filename, "contentType": content_type}
    for name, data in (("request", request), ("response", {"status": status, "body": body})):
        (target / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
        )
    return target
