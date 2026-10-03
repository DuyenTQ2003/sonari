"""A pronunciation backend that needs no NLTK data and no model."""

from collections.abc import Mapping, Sequence


class FakeBackend:
    """Dictionary and predictions given as ARPAbet strings; records what was predicted."""

    def __init__(
        self,
        dictionary: Mapping[str, str] | None = None,
        predictions: Mapping[str, str] | None = None,
    ) -> None:
        self._dictionary = {w: p.split() for w, p in (dictionary or {}).items()}
        self._predictions = {w: p.split() for w, p in (predictions or {}).items()}
        self.predicted: list[str] = []

    def lookup(self, word: str) -> Sequence[str] | None:
        return self._dictionary.get(word)

    def predict(self, word: str) -> Sequence[str]:
        self.predicted.append(word)
        return self._predictions.get(word, [])
