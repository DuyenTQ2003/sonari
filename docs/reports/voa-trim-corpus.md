# The trimmed corpus

The last trimming step. The open-slot rules of the recall round are gone (ADR-0008 5.3 stands), three exact
quick wins are in, precision and recall are measured again on the rules as they now are, and the trimmed corpus
is written at the cap of ADR-0008 decision 2: **5%**. Read-only on `~/sonari-data`; the parser, the thresholds
and the Flesch-Kincaid formula are untouched. Every line and passage read is in
[voa-trim-final-labels.tsv](voa-trim-final-labels.tsv).

```bash
make voa-trim       # about 90 s; writes ~/sonari-trimmed/voa/trimmed.jsonl and MANIFEST.json (cap 5%)
```

A first version of this report wrote the corpus at 10% (PR #38). The maintainer then decided the cap stays at
5%, as ADR-0008 says, and the corpus was written again; the 10% figures below are the measured alternative, not
what is written.

## Result

**724 passages are written, each cut by at most 5% of its words, whole lines only.** About 409 of them (330 to
484) are free of a frame line the lists miss; the level 4 MVP needs roughly 50. 48 are usable as they are, with
nothing cut. No removed line was wrong: 0 of the 1,273 lines the corpus removes, and 0 of 300 lines and 0 of 150
long texts drawn at random from the whole removal set.

| Cut at most | Usable | Free of missed frame (95% interval) | Usable and clean | Same, lenient reading |
|---|---|---|---|---|
| as is | 48 (42 outside English-teaching and fiction programmes) | not sampled | - | - |
| 2% of the words | 442 | 60% (45% to 75%) | 265 (199 to 332) | 320 |
| **5% (written)** | **724** (413 topical, 311 English-teaching or fiction) | **57%** (46% to 67%) | **409** (330 to 484) | 509 |
| 10% (not written) | 1,081 | 62% (54% to 71%) | 674 (578 to 766) | 784 |

"Usable" is the filter of [voa-corpus.md](voa-corpus.md): FK below 7, 250 to 1,200 words in the text left after
the cut, VOA-staff licence, not a copy. "Free of missed frame" is the share of a seeded sample of 120 passages
(40, 45 and 35 from the usable-at-2%, 2-5% and 5-10% sets; seed 20261007) that was read in full and has no
frame line left after the trim; the 5% figures use its first two strata (85 passages). The strict reading counts
a closing that recaps the lesson or asks the reader to practise as frame; the lenient reading does not (13 of
the 47 unclean passages of the whole sample have only such lines). 95% bootstrap intervals, 4,000 draws, seed 1.

**Usable per unit** (crude keyword tags on title and lead; a passage can match several units or none; from
[voa-corpus.md](voa-corpus.md)):

| Unit | as is | up to 5% (written) | up to 10% (not written) |
|---|---|---|---|
| Healthy habits | 4 | **52** | 78 |
| Study and work | 15 | **126** | 217 |
| Food and eating | 1 | **63** | 104 |
| Technology | 4 | **62** | 65 |
| Animals | 2 | **42** | 68 |
| Music | 0 | **47** | 53 |
| Nature and places | 3 | **48** | 54 |
| Sport | 1 | **28** | 37 |

The thinnest unit, Sport, has 28 usable passages at 5%, against 6 that the units proposal asks for. Clean
passages per unit were not sampled; scaling by the overall 57% would still leave about 16 for Sport.

## What changed, and what it cost

**The open-slot rules are out.** ADR-0008 5.3 asks for the variable part of a rule to come from a closed list.
Round two had added rules with a bounded open slot; the maintainer decided not to keep them
([ADR-0008 Notes](../adr/0008-boilerplate-trimming-removes-whole-lines-only.md)). Removed: the reader-question
rule and the neighbour rule of `classify_all` (a question inside or beside an invitation to comment), the
glossary rule (a headword, a dash, a part of speech, a definition) and ten sentence patterns (a call to comment
with any words around a verb and a channel, two patterns; an address after "Our e-mail address is"; a click or
download line; an opener with any words around a programme title; a credit with any noun after "wrote this",
two patterns; a report name before "was written by"; the topic of a VITA leaflet; anything after "read the
passage"). Kept: five sentence grammars made of fixed alternations ("On this program we explore ...", two VITA
lines, "<name> was the editor", "<name> produced the video"), the broadcast date line, and the stage direction
`(MUSIC: ...)`: its keyword and colon identify it and its variable part sits inside parentheses, so the text
marks the boundary. A test fails if any other rule gains a repeated character class or a wildcard.

| Lines the removal set lost (corpus-wide, 74,965 to 70,441 after the quick wins) | Lines |
|---|---|
| glossary entries ("tradition - n. a way of thinking ...") | 1,923 |
| invitation lines with a question to the reader ("Do you have rodeos where you live? Let us know ...") | 2,222 |
| question lines beside an invitation | 54 |
| other open sentence rules (opener, credit, contact line) | 369 |

**Three quick wins, each with its evidence (ADR-0008 5).** Curly double quotes around a title broke the
`<prog>` slot (`“Words and Their Stories.”`); `normalise` now drops double quotes, which adds 12 lines. The page
header "Read and listen to the article. Then open the activities on the right side of the page to improve your
English!" is listed (31 lines), and so is "(The story continues next week)" (1 line). The 44 lines are all in the
labels file and all read: frame. Tests: `test_corpus_slots.py`, `test_corpus_page_lines.py` (each with the
nearest content it must keep). The apostrophes were already folded, so the bug is the double quote, not the
apostrophe.

**One more finding, fixed and kept.** Writing the corpus checked each record against the rules of the report,
and one passage had 235 words once its page furniture ("Share", "Print", "Follow us") was cut: the length window
counted those words as words of the passage. ADR-0008 says the window applies to the text left, and the trim
removes furniture, so `Passage.text_words` holds the words of the text left and the window uses it after a cut.
**It moves the count by at most one passage; no threshold changes.** At 2% and at 10% the count falls by one; at
5% one passage leaves (a *Let's Learn English* lesson that drops to 235 words) and another enters (a 1,241-word
*This Is America* passage whose furniture takes it under 1,200), so the count stays 724 and the membership
changes by one.

| Usable at | as is | 2% | 5% | 10% |
|---|---|---|---|---|
| round two (open slots), `527e7e4` | 55 | 368 | 678 | 1,123 |
| open slots removed | 57 | 451 | 730 | 1,082 |
| plus the three quick wins | 48 | 443 | 724 | 1,082 |
| plus the length window on the text left (now) | 48 | 442 | 724 | 1,081 |

The usable count moves both ways because it only sees what the lists recognise: a line the rules no longer
know is not counted against the cap, so more passages fit under 2% and 5%, and they are less clean. The count
that means something is the one in the Result table. Round two measured 276, 462 and 793 passages usable and
clean at 2%, 5% and 10% (75%, 68% and 71%). The two samples are independent draws read under one rubric, so the
drop is clear in direction and imprecise in size: at 5% the intervals overlap (58% to 78% then, 46% to 67% now).
Reading the new sample leniently gives 509 at 5%, above round two's 462 and the strict 409: how closings are
counted moves the figure about as much as the open slots did.

## Precision

The 2% gate and the standing result of no error hold.

| Set | What was read | Wrong |
|---|---|---|
| A, the corpus that is written | every distinct text among the 1,273 lines removed from the 724 passages (283 texts, 3 of them above 20 words) | 0 of 1,273 lines |
| B, the whole removal set | 300 lines drawn at random from 70,441 (252 of up to 10 words, 39 of 11-20, 9 above 20; seed 20261008) | 0 of 300: 0 to 1.2% |
| C, where content hides | 150 of the 1,119 distinct removed texts above 20 words (seed 20261008) | 0 of 150: 0 to 2.4% |
| the quick wins | all 44 lines they add | 0 |

Set A was read as a census of the wider 10% set (531 texts, 2,646 lines); every text of the 5% corpus is one of
them. The lines removed are programme 418, presenter 673, script 76 and call to comment 106. The furniture lines
the trim also removes (1,262 in the corpus: "Share", "Print", "Follow us", "Return to main page") are page
layout and were not read one by one; they are one anchored pattern of `boilerplate.tsv`. Every removed line of
the corpus is stored with its rule, so any of them can be read later.

## Why the cap stays at 5%

The maintainer's decision, on this evidence:

- **A wider cap buys passages nobody needs.** The 10% cap adds 357 passages, 255 of them from programmes about
  English or from fiction (*Words and Their Stories* alone is about half), which the units proposal ruled out as
  topical sources, and only 102 topical ones. At 5% every one of the eight units already has at least 28 usable
  passages (28 to 126), against 6 that the proposal asks for, and about 409 passages free of missed frame against
  a need of about 50. It adds most where there was most (Study and work 126 to 217) and 3 to 9 where a unit was
  thinnest (Technology 62 to 65, Sport 28 to 37).
- **A wider cap gives every future rule error more room to cut.** The risk ADR-0008 named is the long lines: 73
  of the 78 lines above 20 words that the 10% corpus removes are in the 5-10% band, and a passage there loses a
  median 6.4% of its words, against 1.3% at 5%. No error was found in them (the 45 distinct long texts were all
  read), but the lists are read by one person and will change; a wrong rule costs less text at 5%.
- **The cap is stored, not baked in.** Every record has `trim.cap` and `trim.removed_share`, and `--cap` of
  `make voa-trim` writes another one. Moving to 10% later is a rerun; nothing in ADR-0008 changes.

## The corpus

- **Where:** `~/sonari-trimmed/voa/` (`$TRIM_DIR`), outside the read-only `~/sonari-data`. The writer refuses to
  write inside the cache. `trimmed.jsonl` is 5.9 MB, one JSON object per passage in URL order; `MANIFEST.json`
  has the counts, the snapshot of `index.jsonl` (47,860 rows, sha256 `861377466176...`), the rules version and the
  sha256 of `trimmed.jsonl`. Two runs give the same bytes.
- **Record:** `url`, `title`, `program`, `words`, `fk` (of the text left), `original_text` (the lines as the
  parser returns them), `text` (what everything else reads: the original minus the removed lines), and
  `trim`: `rules_version`, `cap`, `removed_words`, `removed_share`, `removed` (a list of `{index, kind, rule,
  text}`, the 0-based index in `original_text`). Both texts are lists of lines. `original_text` is the parser's
  body: it already leaves out the parser's own credit lines and the "Words in This Story" glossary.
- **Numbers:** 724 passages; 1,273 lines removed (by kind: presenter 673, programme 418, call to comment 106,
  script 76) plus 1,262 furniture lines; 7,805 words cut. In a passage that needs a trim (676 do), the median
  trim is 2 lines and 1.6% of the words (p90: 3 lines, 4.1%); 48 passages lose only furniture. The largest cut is
  4.99%.
- **Rules version:** `voa-trim/163aae96e072`, a digest of the lists, the patterns and the classifier, so any
  change to them is a new version. No rule changed in this step.
- **Checked:** a test (`test_corpus_write_trimmed.py`) and a one-off verifier that does not use the writer read the
  file back: for every record `text` is `original_text` minus the removed indexes, in order, byte for byte; each
  removed record is the line it says; no record is over the cap; the text is 250 to 1,200 words with FK below 7.
  The writer also stops if its removed words differ from the report's. The 724 records pass.
- **Not in it:** passages that are not usable at 5%, and the glossary. Ingestion into the `content` context's
  `Source` is the next step (ADR-0008 decision 3 names the fields; `original_text` and `text` are lists here
  and a join with newlines there).

## Limits

- One labeller, who also wrote the lists and the rules. The census and the samples are a second reading by the
  same person; the recall reading is a judgement of what counts as frame. The strict and the lenient columns
  bracket the main one: closings that recap the lesson or ask the reader to practise are the borderline.
- The recall sample is a fresh draw under frozen rules, but the lists were built from this corpus, so the figures
  describe this corpus and not new VOA text. The 5% figures rest on 85 passages: intervals about 20 points wide.
- The sample was drawn before the length-window fix. None of the 3 passages that the fix moved was in it; the one
  that entered was read as a census (unclean) and counted that way.
- Recall stops here: the 90% target was withdrawn. What is left unlisted is mostly closings, teasers, blurbs and
  practice prompts in *Everyday Grammar*, *Ask a Teacher* and *Words and Their Stories*; the families are in
  [voa-trim-recall.md](voa-trim-recall.md).
