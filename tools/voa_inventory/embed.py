"""Embedding tagger: bge-m3 against a short description per topic.

Title + first paragraph are embedded and compared (cosine) with the `description` of every
topic and candidate and with the `other` descriptions of off-topic content in topics.yaml.
The item takes the single nearest description if that is a topic or candidate and its
similarity reaches `min_similarity`; nearest to an `other` description means untagged.

torch and transformers are imported only when the model is loaded, so the assignment logic
below runs (and is tested) with numpy alone.
"""

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import yaml

from voa_inventory.topics import TOPICS_PATH, Catalog, Tags, load_catalog

Encoder = Callable[[Sequence[str]], np.ndarray]


def assign(sims: np.ndarray, kinds: Sequence[str], ids: Sequence[str], floor: float) -> Tags:
    """Tags for one item given its similarity to every description.

    `kinds[i]` is "topic", "candidate" or "other"; `ids[i]` the topic id.
    """
    best = int(np.argmax(sims))
    if kinds[best] == "other" or sims[best] < floor:
        return Tags()
    score = {ids[best]: float(sims[best])}
    return Tags(topics=score) if kinds[best] == "topic" else Tags(candidates=score)


def bge_encoder(model_name: str, max_tokens: int, batch_size: int = 16) -> Encoder:
    """Dense bge-m3 embeddings (CLS vector, L2-normalised) on CPU."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).eval()

    def encode(texts: Sequence[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), batch_size):
            batch = tokenizer(
                list(texts[i : i + batch_size]),
                padding=True,
                truncation=True,
                max_length=max_tokens,
                return_tensors="pt",
            )
            with torch.inference_mode():
                cls = model(**batch).last_hidden_state[:, 0]
            out.append(torch.nn.functional.normalize(cls, dim=-1).numpy())
        return np.concatenate(out).astype(np.float32)

    return encode


class EmbeddingTagger:
    name = "bge-m3"
    tags_only_usable = True  # embedding thousands of pages nobody will count is wasted time

    def __init__(
        self,
        path: Path = TOPICS_PATH,
        encode: Encoder | None = None,
        catalog: Catalog | None = None,
    ) -> None:
        cfg = yaml.safe_load(path.read_text("utf-8"))["embedding"]
        self.floor = float(cfg["min_similarity"])
        catalog = catalog or load_catalog(path)
        self._ids, self._kinds, descriptions = [], [], []
        for kind, metas in (("topic", catalog.topics), ("candidate", catalog.candidates)):
            for meta in metas:
                self._ids.append(meta.id)
                self._kinds.append(kind)
                descriptions.append(meta.description)
        for i, text in enumerate(catalog.other):
            self._ids.append(f"other_{i}")
            self._kinds.append("other")
            descriptions.append(text.strip())
        self._encode = encode or bge_encoder(cfg["model"], int(cfg["max_tokens"]))
        self._prototypes = self._encode(descriptions)

    def tag_all(self, pairs: Sequence[tuple[str, str]]) -> list[Tags]:
        if not pairs:
            return []
        vectors = self._encode([f"{title}\n{para}" for title, para in pairs])
        sims = vectors @ self._prototypes.T
        return [assign(row, self._kinds, self._ids, self.floor) for row in sims]
