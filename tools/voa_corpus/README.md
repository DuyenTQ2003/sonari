# VOA corpus measurement

Measures the whole cached VOA Learning English corpus: size, length, readability, vocabulary
against a CEFR list, boilerplate, topics, and how many passages pass the level 4 filter. The
result is `docs/reports/voa-corpus.md`.

```bash
make voa-corpus                 # wordlists, then the measurement (about 90 s), then the report
make voa-corpus ARGS=--cache=/other/voa_cache
```

Read-only on `$DATA_DIR/voa_cache` (default `~/sonari-data`); deterministic; no network except the
word list; no LLM. It reuses `voa_inventory` for parsing, the licence check and the grade formula.

| File | Job |
|---|---|
| `analyze.py` | The command: measures every page in URL order, builds the tables, rewrites the report |
| `measure.py` | One page: length, grades, vocabulary levels, boilerplate paragraphs, topic tags |
| `filters.py` | The level 4 filter (`blockers`), its thresholds and the report's buckets |
| `boilerplate.py`, `boilerplate.tsv`, `frames/` | Which lines are not the passage (ADR-0008): page furniture (one anchored pattern), and frame lines. `classify` says what a line is; `classify_all` also looks at the neighbours of a paragraph list (a question line beside an invitation to comment). A line is frame only when every sentence in it is on a closed list (`frames/*.txt`, with staff names in `staff.txt`, programme titles in `programmes.txt` and report topics in `report_topics.txt` as slots) or matches an anchored rule in `frames/patterns.tsv` |
| `wordlist.py`, `irregular.txt`, `wordlists.sha256` | CEFR-J 1.5 + Octanove C1/C2, loaded from `~/.cache/sonari/wordlists` by `make voa-wordlists` |
| `units.tsv` | Crude keywords for the eight level 4 units |
| `missing.py`, `docs/reports/voa-missing-labels.tsv` | `make voa-missing`: the seeded sample of text-less pages with its hand labels, and a census of the article text the parser never reads (report: `voa-missing-pages.md`) |

The word list is downloaded, not committed: the CEFR-J terms allow use with a citation but say
nothing about redistribution (cite: *The CEFR-J Wordlist Version 1.5*, compiled by Yukio Tono,
Tokyo University of Foreign Studies; the C1/C2 list is Octanove Labs, CC BY-SA 4.0).

To change a threshold, edit `filters.py`. To change what counts as boilerplate, add to a list in `frames/`
only with the evidence ADR-0008 section 5 asks for (the matches listed, read, and tested against the negative
cases in `tests/test_corpus_negative_cases.py`); `tests/test_corpus_frames.py` checks that every entry is in the
form the classifier looks up, `tests/test_corpus_patterns.py` that every rule is anchored at both ends and keeps
its nearest content, and `tests/test_corpus_slots.py` the slots. `docs/reports/voa-trim-precision.md` says how
often the lists are wrong and `docs/reports/voa-trim-recall.md` how much frame they still miss.
