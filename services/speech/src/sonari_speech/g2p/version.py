"""Which rules turned text into expected phonemes, so a stored result can say it is stale."""

import hashlib

from sonari_speech.g2p.lexicon import LEXICON_PATH
from sonari_speech.phoneset.mapping import TABLE_PATH


def g2p_version() -> str:
    """A digest of the lexicon overrides and the ARPAbet-to-espeak table. It does not cover the
    CMUdict or g2p_en: those are pinned by the lock file, and a change there shows up when the
    stored phonemes are recomputed and compared."""
    digest = hashlib.sha256(LEXICON_PATH.read_bytes() + TABLE_PATH.read_bytes()).hexdigest()
    return f"g2p/{digest[:12]}"
