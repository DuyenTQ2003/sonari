"""Reference text -> expected espeak tokens, per word.

pronouncer = Pronouncer(G2pEnBackend())          # loads g2p_en once, about 2 s
words = pronouncer.pronounce("I don't think so")  # one WordPron per word, with spans
"""

from sonari_speech.g2p.backend import G2pDataMissing, G2pEnBackend
from sonari_speech.g2p.pronouncer import Pronouncer, PronunciationBackend, WordPron

__all__ = ["G2pDataMissing", "G2pEnBackend", "Pronouncer", "PronunciationBackend", "WordPron"]
