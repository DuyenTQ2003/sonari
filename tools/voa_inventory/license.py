"""Licence filter for VOA pages (ADR-0006): VOA-staff byline, no wire text, no third-party media.

Deliberately conservative: an unknown byline, any mention of a wire service in the text,
and any wire or stock-agency credit on an image all exclude the item. Re-check before use
(P50); this only sizes the corpus.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

STAFF_BYLINES = frozenset({"voa learning english", "voa", "voice of america", "voa news"})
# Case-sensitive on purpose: "AP" and "AFP" are wire codes, "ap" is not.
WIRE = re.compile(r"\b(Associated Press|Reuters|Agence France[- ]Presse|AFP|AP)\b")
STOCK = re.compile(r"\b(Getty Images|Shutterstock|Alamy|iStock)\b")


@dataclass(frozen=True)
class Verdict:
    license_ok: bool
    reasons: tuple[str, ...]


def judge(
    byline: str, credit_line: str, body: Sequence[str], image_credits: Sequence[str]
) -> Verdict:
    """`body` excludes the credit paragraphs; `image_credits` are alt texts and captions."""
    reasons = []
    if byline.strip().lower() not in STAFF_BYLINES:
        reasons.append("byline_not_staff")
    if WIRE.search(credit_line):
        reasons.append("wire_credit")
    if any(WIRE.search(p) for p in body):
        reasons.append("wire_mention")
    if any(WIRE.search(c) or STOCK.search(c) for c in image_credits):
        reasons.append("third_party_media")
    return Verdict(not reasons, tuple(reasons))
