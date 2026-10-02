"""Shared test markers."""

import os
import shutil

import pytest

# In CI the speech job installs ffmpeg, so a missing one must fail there, not skip.
needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None and not os.environ.get("CI"), reason="ffmpeg is not installed"
)
