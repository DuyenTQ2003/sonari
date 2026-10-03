"""The runtime P22/P23 call: recording bytes in, trimmed audio and log-posteriors out.

    runtime = SpeechRuntime(Settings()); await runtime.start()   # load + warm up
    analysis = await runtime.analyse(upload_bytes)              # decode, trim, infer

`start` never raises: a model that cannot be loaded leaves the process up with
`ready == False` and the reason in `failure`, which /readyz reports. `analyse` goes
through the gate, so overload is a fast 503 with Retry-After, not a long queue.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

from sonari_speech.errors import AppError, MessageKey
from sonari_speech.runtime.audio import SAMPLE_RATE, decode_audio
from sonari_speech.runtime.gate import InferenceGate
from sonari_speech.runtime.model import ModelSession
from sonari_speech.runtime.vad import trim_silence
from sonari_speech.runtime.weights import (
    DEFAULT_MODEL,
    WeightsUnavailable,
    is_valid,
    load_manifest,
)
from sonari_speech.settings import Settings

logger = logging.getLogger(__name__)

ModelFactory = Callable[[Settings], ModelSession]


@dataclass(frozen=True, slots=True)
class Analysis:
    samples: np.ndarray  # the trimmed 16 kHz mono audio that the model saw
    log_probs: np.ndarray  # float32 [frames, vocab], 20 ms per frame
    speech_start_s: float  # where the speech starts in the original recording
    speech_s: float
    total_s: float  # length of the original recording


def load_pinned_model(settings: Settings) -> ModelSession:
    """Load the model file after checking it is exactly the one in models.yaml."""
    spec = load_manifest()[DEFAULT_MODEL]
    if not is_valid(settings.model_path, spec):
        raise WeightsUnavailable(
            f"{settings.model_path} is missing or is not the pinned model "
            f"(sha256 {spec.sha256}); run `python -m sonari_speech.runtime.weights`"
        )
    return ModelSession.load(settings.model_path, settings.intra_op_threads)


class SpeechRuntime:
    def __init__(self, settings: Settings, model_factory: ModelFactory = load_pinned_model) -> None:
        self.settings = settings
        self._factory = model_factory
        self._gate = InferenceGate(settings.slots, settings.in_flight_limit, settings.retry_after_s)
        self._executor = ThreadPoolExecutor(settings.slots, thread_name_prefix="infer")
        self._model: ModelSession | None = None
        self.failure: str | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    async def start(self) -> None:
        """Load the model and run one warm-up inference; only then is the runtime ready."""
        loop = asyncio.get_running_loop()
        try:
            model = await loop.run_in_executor(self._executor, self._factory, self.settings)
            seconds = await loop.run_in_executor(self._executor, model.warmup)
        except Exception as err:  # the process must stay up to say why it is not ready
            self.failure = f"{type(err).__name__}: {err}"
            logger.error("model failed to load: %s", self.failure)
            return
        self._model = model
        self.failure = None
        logger.info(
            "model ready: cores=%d slots=%d in_flight_limit=%d, warm-up inference %.0f ms",
            self.settings.cores,
            self.settings.slots,
            self.settings.in_flight_limit,
            seconds * 1000,
        )

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def analyse(self, data: bytes) -> Analysis:
        """Decode an upload, trim the silence, run the model. Raises AppError on bad input."""
        model = self._model
        if model is None:
            raise AppError(
                503,
                "not_ready",
                MessageKey.NOT_READY,
                headers={"Retry-After": str(self.settings.retry_after_s)},
            )
        async with self._gate.slot():
            samples = await decode_audio(data, self.settings)
            trimmed = trim_silence(samples)
            if trimmed.speech_s < self.settings.min_speech_s:
                raise AppError(
                    422,
                    "audio_too_short",
                    MessageKey.AUDIO_TOO_SHORT,
                    {"minSeconds": self.settings.min_speech_s},
                )
            log_probs = await asyncio.get_running_loop().run_in_executor(
                self._executor, model.infer, trimmed.samples
            )
        return Analysis(
            trimmed.samples,
            log_probs,
            trimmed.start_s,
            trimmed.speech_s,
            len(samples) / SAMPLE_RATE,
        )
