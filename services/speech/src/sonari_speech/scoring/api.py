"""POST /v1/score: a recording and the sentence it should say in, a verdict per phoneme out.

    curl -F audio=@take.webm -F referenceText="I think so" localhost:8001/v1/score

Pipeline: G2P (reference -> espeak tokens per word, en-us from g2p_en, en-gb from espeak-ng,
and the weak forms of a closed list of function words), the runtime (decode, VAD trim, int8
wav2vec2), forced alignment of the whole sentence once per reference, GOP per phoneme, the
best reference per word (scoring/accents.py), versioned thresholds (correct / unclear / wrong),
then a message key per wrong phoneme (scoring/feedback.py). The Vietnamese text is the client's.
No STT and no language model anywhere: the model's posteriors are read, never decoded.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from opentelemetry import trace

from sonari_speech.errors import AppError, ErrorEnvelope, MessageKey, error_response
from sonari_speech.g2p import G2pEnBackend, Pronouncer, WordPron
from sonari_speech.g2p.espeak import EspeakReference, EspeakUnavailable
from sonari_speech.g2p.weak_forms import Forms, load_weak_forms, weak_references
from sonari_speech.runtime.service import SpeechRuntime
from sonari_speech.scoring import dump
from sonari_speech.scoring.accents import Alternative, score_accents
from sonari_speech.scoring.align import TooFewFrames
from sonari_speech.scoring.contract import ScoreResponse
from sonari_speech.scoring.feedback import explain_words
from sonari_speech.scoring.gop import load_thresholds, load_vocab

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("sonari_speech")

MAX_REFERENCE_CHARS = 300
PronouncerFactory = Callable[[], Pronouncer]
BritishFactory = Callable[[], EspeakReference]


def load_pronouncer() -> Pronouncer:
    return Pronouncer(G2pEnBackend())


def load_british() -> EspeakReference:
    return EspeakReference(load_vocab().ids, voice="en-gb")


def british_forms(british: EspeakReference, words: list[WordPron]) -> list[tuple[str, ...] | None]:
    try:
        return british.tokens(words)
    except EspeakUnavailable as err:
        logger.error("en-gb reference failed, scoring en-us only: %s", err)
        return [None] * len(words)


class Scorer:
    """G2P plus the runtime plus GOP. G2P loads in the background (about 2 s), like the model."""

    def __init__(
        self,
        runtime: SpeechRuntime,
        pronouncer_factory: PronouncerFactory = load_pronouncer,
        british_factory: BritishFactory = load_british,
    ) -> None:
        self.runtime = runtime
        self._factory = pronouncer_factory
        self._british_factory = british_factory
        self._pronouncer: Pronouncer | None = None
        self._british: EspeakReference | None = None
        self._weak: Forms | None = None
        self.failure: str | None = None

    @property
    def ready(self) -> bool:
        return None not in (self._pronouncer, self._british, self._weak)

    async def start(self) -> None:
        """Load both G2Ps and the weak forms; a failure leaves the process up and not ready."""
        try:
            self._british = await asyncio.to_thread(self._british_factory)
            self._pronouncer = await asyncio.to_thread(self._factory)
            self._weak = load_weak_forms(load_vocab().ids)
        except Exception as err:
            self.failure = f"{type(err).__name__}: {err}"
            logger.error("g2p failed to load: %s", self.failure)

    async def score(self, data: bytes, reference_text: str) -> ScoreResponse:
        pronouncer, british, weak = self._pronouncer, self._british, self._weak
        if pronouncer is None or british is None or weak is None:
            retry = str(self.runtime.settings.retry_after_s)
            raise AppError(503, "not_ready", MessageKey.NOT_READY, headers={"Retry-After": retry})
        words = pronouncer.pronounce(reference_text)
        if not any(word.tokens for word in words):
            raise AppError(422, "reference_unpronounceable", MessageKey.VALIDATION)
        # espeak-ng (about 12 ms) runs while the model does.
        analysis, gb_tokens = await asyncio.gather(
            self.runtime.analyse(data), asyncio.to_thread(british_forms, british, words)
        )
        thresholds = load_thresholds()
        alternatives: list[Alternative] = [("en-gb", gb_tokens)]
        alternatives += [("en-us", ref) for ref in weak_references(words, weak)]
        with tracer.start_as_current_span("speech.score") as span:
            span.set_attribute("score.words", len(words))
            span.set_attribute("score.phonemes", sum(len(w.tokens) for w in words))
            span.set_attribute("score.thresholds_version", thresholds.version)
            span.set_attribute("score.words_en_gb_form", sum(t is not None for t in gb_tokens))
            span.set_attribute("score.references", len(alternatives) + 1)
            try:
                scored = await asyncio.to_thread(
                    score_accents,
                    words,
                    alternatives,
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
            thresholds_version=thresholds.version,
            reference_text=reference_text,
            words=explain_words(scored),
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
    root = request.app.state.dump_dir
    if root is None:
        return await scorer.score(data, reference_text)
    status, body = 500, None
    try:
        result = await scorer.score(data, reference_text)
        status, body = 200, result.model_dump(mode="json", by_alias=True)
        return result
    except AppError as err:
        status = err.status_code
        response = error_response(err.status_code, err.code, err.message_key, err.details)
        body = json.loads(bytes(response.body))
        raise
    finally:
        saved: Any = (data, audio.filename, audio.content_type, reference_text, status, body)
        await asyncio.to_thread(dump.save, root, *saved)
