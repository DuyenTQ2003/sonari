"""Measure one cached VOA page: size, readability, vocabulary levels and boilerplate."""

import gzip
import hashlib
import re
import zlib
from collections import Counter
from functools import cache
from pathlib import Path

from voa_inventory.levels import SENTENCE_END, WORD, stats
from voa_inventory.parse import parse_page

from voa_corpus import wordlist
from voa_corpus.filters import MIN_PASSAGE_WORDS, Passage
from voa_corpus.trim import trim

TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
CONTRACTION = {"ca": "can", "wo": "will", "sha": "shall"}  # "can't" -> ca + n't
LOOSE_WORDS = 20
# (unit, pattern): crude keyword tags for the eight level 4 units, matched at the start of a word on
# the title and the lead paragraph. The lists (units.tsv) say where to look, not how many exist.
UNITS = [
    (name, re.compile(rf"\b(?:{words})", re.I))
    for name, words in (
        line.split("\t")
        for line in Path(__file__).with_name("units.tsv").read_text("utf-8").splitlines()
        if line and not line.startswith("#")
    )
]
STATE: dict = {}


def init(cache: Path, wordlist_dir: Path) -> None:
    """Pool initializer: where the cache is and the word list (loaded once per process)."""
    STATE["cache"], STATE["table"] = cache, wordlist.load(wordlist_dir)


@cache
def token_class(word: str, initial: bool) -> int:
    """0-5 = A1..C2, 6 = in neither list, 7 = proper noun or acronym (judged by capitals)."""
    low = word.replace("’", "'").lower()
    base = CONTRACTION.get(low[:-3], low[:-3]) if low.endswith("n't") else low.split("'")[0]
    level = wordlist.level_of(base, STATE["table"])
    if len(word) == 1 and low not in ("a", "i"):  # a letter of an acronym or an initial
        return 7
    if (word[0].isupper() and (not initial or level is None)) or (word.isupper() and len(word) > 1):
        return 7
    return 6 if level is None else level


def measure(entry: tuple[str, str]) -> Passage:
    url, file = entry
    try:
        raw = gzip.decompress((STATE["cache"] / file[:2] / file).read_bytes())
    except (OSError, EOFError, zlib.error):
        return Passage(url, html_ok=False)
    item, body = parse_page(raw.decode("utf-8", "replace"), url)
    p = Passage(
        url,
        program=item.program,
        words=item.word_count,
        licence_ok=item.license_ok,
        has_audio=item.has_audio,
        html_ok=raw.rstrip().endswith(b"</html>"),
    )
    if p.words < MIN_PASSAGE_WORDS:
        return p
    paras = body.paragraphs
    t = trim(paras)  # the one trim: what is counted here is what the trimmed corpus stores
    loose = []
    for para, hit in zip(paras, t.hits, strict=True):
        if hit:
            p.boiler[hit[0]] = p.boiler.get(hit[0], 0) + hit[1]
        elif len(para.split()) <= LOOSE_WORDS:
            loose.append(re.sub(r"\s+", " ", para.strip().lower()))
    p.kept = t.kept_frame_words  # frame words on a line that stays whole: a trim cannot cut them
    plain = t.kept  # a speaker label leaves its quotation
    words, _, p.fk = stats(plain)  # the passage as it would be read, boilerplate left out
    p.text_words = words
    sentences = [s for para in plain for s in SENTENCE_END.split(para.strip()) if WORD.search(s)]
    letters = sum(len(re.findall("[A-Za-z]", w)) for para in plain for w in WORD.findall(para))
    p.sentences, p.fk_raw = len(sentences), item.fk_grade
    if words and sentences:
        p.cl = 5.88 * letters / words - 29.6 * len(sentences) / words - 15.8  # Coleman-Liau
    p.digest = hashlib.sha1("\n".join(paras).encode()).hexdigest()
    vocab, unlisted = [0] * 8, Counter()
    for para in plain:
        for sentence in SENTENCE_END.split(para.strip()):
            for i, word in enumerate(TOKEN.findall(sentence)):
                level = token_class(word, i == 0)
                vocab[level] += 1
                if level == 6:
                    unlisted[word.lower()] += 1
    p.vocab, p.unlisted, p.loose = tuple(vocab), dict(unlisted), tuple(loose)
    lead = f"{item.title} {item.first_paragraph[:400]}"
    p.units = tuple(i for i, (_, rx) in enumerate(UNITS) if rx.search(lead))
    return p
