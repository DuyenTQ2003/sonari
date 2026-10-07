"""POST /v1/score: a recording and the sentence it should say in, a verdict per phoneme out.

    curl -F audio=@take.webm -F referenceText="I think so" localhost:8001/v1/score

Pipeline: G2P (reference -> espeak tokens per word), the runtime (decode, VAD trim, int8
wav2vec2), forced alignment of the whole sentence, GOP per phoneme, versioned threshold.
No STT and no language model anywhere: the model's posteriors are read, never decoded.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from opentelemetry import trace

from sonari_speech.errors import AppError, ErrorEnvelope, MessageKey
from sonari_speech.g2p import G2pEnBackend, Pronouncer
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.scoring.align import TooFewFrames
from sonari_speech.scoring.contract import ScoreResponse
from sonari_speech.scoring.gop import load_thresholds, load_vocab, score_words

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("sonari_speech")

MAX_REFERENCE_CHARS = 300
PronouncerFactory = Callable[[], Pronouncer]


def load_pronouncer() -> Pronouncer:
    return Pronouncer(G2pEnBackend())


class Scorer:
    """G2P plus the runtime plus GOP. G2P loads in the background (about 2 s), like the model."""

    def __init__(
        self, runtime: SpeechRuntime, pronouncer_factory: PronouncerFactory = load_pronouncer
    ) -> None:
        self.runtime = runtime
        self._factory = pronouncer_factory
        self._pronouncer: Pronouncer | None = None
        self.failure: str | None = None

    @property
    def ready(self) -> bool:
        return self._pronouncer is not None

    async def start(self) -> None:
        """Load G2P; like the model, a failure leaves the process up and not ready."""
        try:
            self._pronouncer = await asyncio.to_thread(self._factory)
        except Exception as err:
            self.failure = f"{type(err).__name__}: {err}"
            logger.error("g2p failed to load: %s", self.failure)

    async def score(self, data: bytes, reference_text: str) -> ScoreResponse:
        pronouncer = self._pronouncer
        if pronouncer is None:
            retry = str(self.runtime.settings.retry_after_s)
            raise AppError(503, "not_ready", MessageKey.NOT_READY, headers={"Retry-After": retry})
        words = pronouncer.pronounce(reference_text)
        if not any(word.tokens for word in words):
            raise AppError(422, "reference_unpronounceable", MessageKey.VALIDATION)
        analysis = await self.runtime.analyse(data)
        thresholds = load_thresholds()
        with tracer.start_as_current_span("speech.score") as span:
            span.set_attribute("score.words", len(words))
            span.set_attribute("score.phonemes", sum(len(w.tokens) for w in words))
            span.set_attribute("score.thresholds_version", thresholds.version)
            try:
                scored = await asyncio.to_thread(
                    score_words,
                    words,
                    analysis.log_probs,
                    analysis.speech_start_s,
                    thresholds,
                    load_vocab(),
                )
            except TooFewFrames:
                # The speech cannot hold the sentence: the learner said much less than it.
                raise AppError(
                    422,
                    "audio_too_short",
                    MessageKey.AUDIO_TOO_SHORT,
                    {"reason": "shorter_than_reference"},
                ) from None
        return ScoreResponse(
            thresholds_version=thresholds.version, reference_text=reference_text, words=scored
        )


router = APIRouter()


@router.post(
    "/v1/score",
    response_model=ScoreResponse,
    responses={code: {"model": ErrorEnvelope} for code in (413, 415, 422, 503)},
)
async def score(
    request: Request,
    audio: Annotated[UploadFile, File()],
    reference_text: Annotated[
        str, Form(alias="referenceText", min_length=1, max_length=MAX_REFERENCE_CHARS)
    ],
) -> ScoreResponse:
    scorer: Scorer = request.app.state.scorer
    # One byte over the limit is enough for decode_audio to refuse it with 413.
    data = await audio.read(scorer.runtime.settings.max_upload_bytes + 1)
    return await scorer.score(data, reference_text)
