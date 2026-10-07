"""The two slow loads, done once per session: g2p_en (about 2.5 s) and the int8 model."""

import pytest

from sonari_speech.g2p.backend import G2pEnBackend, default_nltk_dir
from sonari_speech.g2p.pronouncer import Pronouncer
from sonari_speech.runtime.model import ModelSession
from sonari_speech.settings import Settings


@pytest.fixture(scope="session")
def real_pronouncer() -> Pronouncer:
    return Pronouncer(G2pEnBackend(default_nltk_dir()))


@pytest.fixture(scope="session")
def real_model() -> ModelSession:
    return ModelSession.load(Settings().model_path, intra_op_threads=1)
