"""Turn one VOA Learning English article page into an inventory record (stdlib only)."""

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser

from voa_inventory.levels import stats
from voa_inventory.license import judge

LD_JSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
CREDIT_NOUN = re.compile(r"\b(this|the) (story|report|article)\b", re.IGNORECASE)
CREDIT_VERB = re.compile(
    r"\b(wrote|written|reported|reporting|adapted|edited|contributed|based on)\b", re.IGNORECASE
)
SEPARATOR = re.compile(r"^_{5,}$")
MP3 = re.compile(r"\.mp3(\?|$)")
# The player's "No media source currently available" overlay, the MP3 download line and
# "Broadcast: <date>" are all <p> tags inside the article container and all short.
MIN_LEAD_WORDS = 20
# Lesson-page boilerplate that is long enough to pass MIN_LEAD_WORDS.
LEAD_BOILERPLATE = re.compile(
    r"^(Read and listen to the article\.|What do you think of this lesson\?)", re.IGNORECASE
)


@dataclass
class Article:
    """What the article container holds, before any judgement."""

    paragraphs: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    image_credits: list[str] = field(default_factory=list)
    audio: list[str] = field(default_factory=list)
    page_audio: list[str] = field(default_factory=list)  # anywhere on the page
    has_container: bool = False


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.article = Article()
        self._depth = 0  # div depth inside #article-content, 0 = outside
        self._buf: list[str] | None = None
        self._kind = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "audio" and MP3.search(a.get("src", "")):
            self.article.page_audio.append(a["src"])
        if self._depth == 0:
            if tag == "div" and a.get("id") == "article-content":
                self._depth = 1
                self.article.has_container = True
            return
        if tag == "div":
            self._depth += 1
        elif tag in ("p", "h2", "h3", "figcaption"):
            self._flush()
            self._buf, self._kind = [], tag
        elif tag == "br" and self._buf is not None:
            self._buf.append(" ")
        elif tag == "img" and a.get("alt"):
            self.article.image_credits.append(a["alt"])
        elif tag in ("audio", "source") and MP3.search(a.get("src", "")):
            self.article.audio.append(a["src"])
        elif tag == "a" and MP3.search(a.get("href", "")):
            self.article.audio.append(a["href"])

    def handle_endtag(self, tag: str) -> None:
        if self._depth == 0:
            return
        if tag == "div":
            self._depth -= 1
        elif tag in ("p", "h2", "h3", "figcaption"):
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._buf is not None:
            self._buf.append(data)

    def _flush(self) -> None:
        if self._buf is None:
            return
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            target = {
                "p": self.article.paragraphs,
                "figcaption": self.article.image_credits,
            }.get(self._kind, self.article.headings)
            target.append(text)
        self._buf = None


@dataclass
class Item:
    url: str
    title: str
    program: str
    date: str
    byline: str
    credit_line: str
    has_audio: bool
    audio_url: str
    word_count: int
    avg_sentence_len: float
    fk_grade: float | None
    first_paragraph: str
    license_ok: bool
    license_reasons: tuple[str, ...]


def _ld(html: str) -> dict:
    for block in LD_JSON.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "headline" in data:
            return data
    return {}


def _meta(html: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+property="{prop}"[^>]*>', html) or re.search(
        rf'<meta[^>]+content="[^"]*"[^>]+property="{prop}"', html
    )
    c = re.search(r'content="([^"]*)"', m.group(0)) if m else None
    return c.group(1) if c else ""


def _fallback_program(html: str) -> str:
    """Media pages (no article container) name the programme in their header."""
    m = re.search(r'<h1 class="title pg-title title--program">(.*?)</h1>', html, re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _fallback_date(html: str) -> str:
    m = re.search(r'<time pubdate="pubdate" datetime="(\d{4}-\d{2}-\d{2})', html)
    return m.group(1) if m else ""


def _title_tag(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    return m.group(1).strip() if m else ""


def _credit_paragraphs(paragraphs: list[str]) -> list[str]:
    return [
        p
        for p in paragraphs
        if len(p.split()) < 60 and CREDIT_NOUN.search(p) and CREDIT_VERB.search(p)
    ]


def _lead_paragraph(body: list[str]) -> str:
    """First real body paragraph (MIN_LEAD_WORDS+ words, not boilerplate), or "" if none."""
    return next(
        (p for p in body if len(p.split()) >= MIN_LEAD_WORDS and not LEAD_BOILERPLATE.match(p)), ""
    )


def parse_item(html: str, url: str) -> Item:
    parser = _ArticleParser()
    parser.feed(html)
    article = parser.article
    ld = _ld(html)
    author = ld.get("author")
    byline = (author.get("name", "") if isinstance(author, dict) else str(author or "")).strip()
    title = unescape(str(ld.get("headline") or _meta(html, "og:title") or _title_tag(html)))

    main: list[str] = []
    for p in article.paragraphs:
        if SEPARATOR.match(p):
            break  # everything after is the "Words in This Story" glossary
        main.append(p)
    credits = _credit_paragraphs(main)
    body = [p for p in main if p not in credits]
    words, per_sentence, fk = stats(body)
    # Audio-first "media" pages have no article container; their player sits elsewhere.
    audio_url = next(
        iter(article.audio or (article.page_audio if not article.has_container else [])), ""
    )
    verdict = judge(byline, " ".join(credits), body, article.image_credits)
    return Item(
        url=url,
        title=title,
        program=unescape(str(ld.get("articleSection") or _fallback_program(html))),
        date=str(ld.get("datePublished") or _fallback_date(html))[:10],
        byline=byline,
        credit_line=" ".join(credits),
        has_audio=bool(audio_url),
        audio_url=audio_url,
        word_count=words,
        avg_sentence_len=round(per_sentence, 2),
        fk_grade=None if fk is None else round(fk, 2),
        first_paragraph=_lead_paragraph(body),
        license_ok=verdict.license_ok,
        license_reasons=verdict.reasons,
    )
