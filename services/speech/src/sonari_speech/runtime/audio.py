"""Uploaded recording -> 16 kHz mono float32, via ffmpeg.

Browsers record in different containers: Chrome WebM/Opus, Firefox Ogg/Opus, Safari and
iPhone MP4/AAC; a test or a script may upload WAV. ffmpeg decodes all of them.

The upload is untrusted, so ffmpeg is not left to guess: the container is recognised from
its first bytes, only those five are accepted, the demuxer is forced with `-f` (a playlist
or a concat script is never opened) and only the `file` protocol is allowed. Decoding stops
one second past the limit, so a long upload costs the same as a short one.
"""

import asyncio
import contextlib
import os
import shutil
import signal
import tempfile
from pathlib import Path

import numpy as np
from opentelemetry import trace

from sonari_speech.errors import AppError, MessageKey
from sonari_speech.settings import Settings

SAMPLE_RATE = 16000
_BYTES_PER_SAMPLE = 4  # float32

tracer = trace.get_tracer("sonari_speech")


class DecoderUnavailable(RuntimeError):
    """ffmpeg cannot be started: a server fault, not a bad upload."""


def sniff_demuxer(data: bytes) -> str | None:
    """ffmpeg demuxer for the container that `data` starts with; None for anything else."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "matroska,webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[4:8] == b"ftyp":
        return "mov,mp4,m4a,3gp,3g2,mj2"
    return None


def ffmpeg_available(settings: Settings) -> bool:
    return shutil.which(settings.ffmpeg_path) is not None


def _rejected(status: int, code: str, key: MessageKey, **details: object) -> AppError:
    return AppError(status, code, key, details or None)


async def decode_audio(data: bytes, settings: Settings) -> np.ndarray:
    """Decode an upload; raises AppError when it is too big, not audio, or too long."""
    with tracer.start_as_current_span("speech.decode") as span:
        span.set_attribute("audio.bytes", len(data))
        if len(data) > settings.max_upload_bytes:
            raise _rejected(
                413,
                "audio_too_large",
                MessageKey.AUDIO_TOO_LARGE,
                maxBytes=settings.max_upload_bytes,
            )
        demuxer = sniff_demuxer(data)
        if demuxer is None:
            raise _rejected(415, "audio_undecodable", MessageKey.AUDIO_UNDECODABLE)
        samples = await _run_ffmpeg(data, demuxer, settings)
        span.set_attribute("audio.seconds", len(samples) / SAMPLE_RATE)
        if len(samples) > settings.max_clip_s * SAMPLE_RATE:
            raise _rejected(
                422, "audio_too_long", MessageKey.AUDIO_TOO_LONG, maxSeconds=settings.max_clip_s
            )
        return samples


async def _run_ffmpeg(data: bytes, demuxer: str, settings: Settings) -> np.ndarray:
    with tempfile.TemporaryDirectory(prefix="sonari-audio-") as tmp:
        # A file, not a pipe: an MP4 with its index at the end cannot be read from stdin.
        source = Path(tmp) / "input"
        source.write_bytes(data)
        cmd = [
            settings.ffmpeg_path,
            *("-nostdin", "-hide_banner", "-loglevel", "error"),
            *("-protocol_whitelist", "file", "-f", demuxer, "-i", str(source)),
            *("-vn", "-sn", "-dn", "-t", str(settings.max_clip_s + 1.0)),
            *("-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,  # its own process group, so a timeout kills children too
            )
        except OSError as err:
            raise DecoderUnavailable(f"cannot start {settings.ffmpeg_path}: {err}") from err
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), settings.decode_timeout_s)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
            raise _rejected(415, "audio_undecodable", MessageKey.AUDIO_UNDECODABLE) from None
    samples = np.frombuffer(out[: len(out) // _BYTES_PER_SAMPLE * _BYTES_PER_SAMPLE], "<f4")
    if proc.returncode != 0 or len(samples) == 0 or not np.isfinite(samples).all():
        raise _rejected(415, "audio_undecodable", MessageKey.AUDIO_UNDECODABLE)
    return samples.astype(np.float32)
