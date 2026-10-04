# The trimmed corpus

The last trimming step. The open-slot rules of the recall round are gone (ADR-0008 5.3 stands), three exact
quick wins are in, precision and recall are measured again on the rules as they now are, and the trimmed corpus
is written. Read-only on `~/sonari-data`; the parser, the thresholds and the Flesch-Kincaid formula are
untouched. Every line and passage read is in [voa-trim-final-labels.tsv](voa-trim-final-labels.tsv).

```bash
make voa-trim       # about 90 s; writes ~/sonari-trimmed/voa/trimmed.jsonl and MANIFEST.json
```

## Result

**1,081 passages are written, each cut by at most 10% of its words, whole lines only.** About 674 of them
(578 to 766) are free of a frame line the lists miss; the level 4 MVP needs roughly 50. No removed line was
wrong: 0 of 2,646 lines in the corpus, 0 of 300 lines and 0 of 150 long texts drawn at random from the whole
removal set.

| Cut at most | Usable | Free of missed frame (95% interval) | Usable and clean | Same, lenient reading |
|---|---|---|---|---|
| as is | 48 | not sampled | - | - |
| 2% of the words | 442 | 60% (45% to 75%) | **265** (199 to 332) | 320 |
| 5% | 724 | 57% (46% to 67%) | **409** (330 to 484) | 509 |
| 10% (the default) | 1,081 | 62% (54% to 71%) | **674** (578 to 766) | 784 |

"Usable" is the filter of [voa-corpus.md](voa-corpus.md): FK below 7, 250 to 1,200 words in the text left after
the cut, VOA-staff licence, not a copy. "Free of missed frame" is the share of a seeded sample of 120 passages
(40, 45 and 35 from the usable-at-2%, 2-5% and 5-10% sets; seed 20261007) that was read in full and has no
frame line left after the trim. The strict reading counts a closing that recaps the lesson or asks the reader to
practise as frame; the lenient reading does not (13 of the 47 unclean passages have only such lines). 95%
bootstrap intervals, 4,000 draws, seed 1.

## What changed, and what it cost

**The open-slot rules are out.** ADR-0008 5.3 asks for the variable part of a rule to come from a closed list.
Round two had added rules with a bounded open slot; the maintainer decided not to keep them
([ADR-0008 Notes](../adr/0008-boilerplate-trimming-removes-whole-lines-only.md)). Removed: the reader-question
rule and the neighbour rule of `classify_all` (a question inside or beside an invitation to comment), the
glossary rule (a headword, a dash, a part of speech, a definition) and ten sentence patterns (a call to comment
with any words around a verb and a channel, two patterns; an address after "Our e-mail address is"; a click or
download line; an opener with any words around a programme title; a credit with any noun after "wrote this",
two patterns; a report name before "was written by"; the topic of a VITA leaflet; anything after "read the
passage"). Kept: five sentence grammars made of fixed
alternations ("On this program we explore ...", two VITA lines, "<name> was the editor", "<name> produced the
video"), the broadcast date line, and the stage direction `(MUSIC: ...)`: its keyword and colon identify it and
its variable part sits inside parentheses, so the text marks the boundary. A test fails if any other rule gains
a repeated character class or a wildcard.

| Lines the removal set lost (corpus-wide, 74,965 to 70,441 after the quick wins) | Lines |
|---|---|
| glossary entries ("tradition - n. a way of thinking ...") | 1,923 |
| invitation lines with a question to the reader ("Do you have rodeos where you live? Let us know ...") | 2,222 |
| question lines beside an invitation | 54 |
| other open sentence rules (opener, credit, contact line) | 369 |

**Three quick wins, each with its evidence (ADR-0008 5).** Curly double quotes around a title broke the
`<prog>` slot (`“Words and Their Stories.”`); `normalise` now drops double quotes, which adds 12 lines. The page
header "Read and listen to the article. Then open the activities on the right side of the page to improve your
English!" is listed (31 lines), and so is "(The story continues next week)" (1 line). The 44
lines are all in the labels file and all read: frame. Tests: `test_corpus_slots.py`, `test_corpus_page_lines.py`
(each with the nearest content it must keep). The apostrophes were already folded, so the bug is the double
quote, not the apostrophe.

**One more finding, fixed.** Writing the corpus checked each record against the rules of the report, and one
passage had 235 words once its page furniture ("Share", "Print", "Follow us") was cut: the length window counted
those words as words of the passage. ADR-0008 says the window applies to the text left, and the trim removes
furniture, so `Passage.text_words` now holds the words of the text left and the window uses it after a cut. It
moves the counts by one passage at each cap (the thresholds are the same).

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
Reading the new sample leniently gives 784 at 10%, close to round two's 793.

## Precision

The 2% gate and the standing result of no error hold.

| Set | What was read | Wrong |
|---|---|---|
| A, the corpus that is written | every distinct text among the 2,646 lines removed from the 1,081 passages (531 texts, 45 of them above 20 words) | 0 of 2,646 lines |
| B, the whole removal set | 300 lines drawn at random from 70,441 (252 of up to 10 words, 39 of 11-20, 9 above 20; seed 20261008) | 0 of 300: 0 to 1.2% |
| C, where content hides | 150 of the 1,119 distinct removed texts above 20 words (seed 20261008) | 0 of 150: 0 to 2.4% |
| the quick wins | all 44 lines they add | 0 |

The furniture lines the trim also removes (2,326 in the corpus: "Share", "Print", "Follow us", "Return to
main page") are page layout and were not read one by one; they are one anchored pattern of `boilerplate.tsv`.
Every removed line of the corpus is stored with its rule, so any of them can be read later.

## Why 10% and not 5%

ADR-0009 records the decision, which is the maintainer's. What the data says about it:

- **Supply is not the reason.** At 5% every one of the eight units has at least 28 usable passages (crude
  keyword tags: 28 to 126), and about 409 passages are free of missed frame against a need of about 50. The
  units proposal asks for 6 per unit.
- **What 10% adds.** 357 passages, 255 of them from programmes about English or from fiction (*Words and Their
  Stories* alone is about half), which the units proposal ruled out as topical sources, and 102 topical ones. By
  unit (usable at 5% and at 10%): Healthy habits 52 and 78, Study and work 126 and 217, Food and eating 63 and
  104, Technology 62 and 65, Animals 42 and 68, Music 47 and 53, Nature and places 48 and 54, Sport 28 and 37. It
  adds most where there was most, and 3 to 9 where a unit was thinnest.
- **What it costs.** The risk ADR-0008 named is the long lines: 73 of the 78 removed lines above 20 words are in
  the 5-10% band, and a passage there loses a median 6.4% of its words, against 1.3% at 5%. That risk was
  measured and was not found: the 45 distinct long texts were all read, and 0 of 150 random long texts and 0
  of 2,646 lines were wrong. It is the cost the ADR's trigger watches (one content line found in the 5-10% band
  sends the default back to 5%).
- **It is a filter away.** Each record stores `trim.removed_share`, so the 724 passages at 5% are the records with
  `removed_share <= 0.05`. Going back costs a query.

## The corpus

- **Where:** `~/sonari-trimmed/voa/` (`$TRIM_DIR`), outside the read-only `~/sonari-data`. The writer refuses to
  write inside the cache. `trimmed.jsonl` is 8.2 MB, one JSON object per passage in URL order; `MANIFEST.json`
  has the counts, the snapshot of `index.jsonl` (47,860 rows, sha256 `861377466176...`), the rules version and the
  sha256 of `trimmed.jsonl`. Two runs give the same bytes.
- **Record:** `url`, `title`, `program`, `words`, `fk` (of the text left), `original_text` (the lines as the
  parser returns them), `text` (what everything else reads: the original minus the removed lines), and
  `trim`: `rules_version`, `cap`, `removed_words`, `removed_share`, `removed` (a list of `{index, kind, rule,
  text}`, the 0-based index in `original_text`). Both texts are lists of lines. `original_text` is the parser's
  body: it already leaves out the parser's own credit lines and the "Words in This Story" glossary.
- **Numbers:** 1,081 passages; 2,646 lines removed (by kind: programme 1,088, presenter 898, script 467, call to
  comment 193) plus 2,326 furniture lines; 19,143 words cut. In a passage
  that needs a trim, the median trim is 2 lines and 2.9% of the words (p90: 4 lines, 7.2%); 48 passages lose
  only furniture.
- **Rules version:** `voa-trim/163aae96e072`, a digest of the lists, the patterns and the classifier, so any
  change to them is a new version.
- **Checked:** a test (`test_corpus_write_trimmed.py`) and a one-off verifier that does not use the writer read the
  file back: for every record `text` is `original_text` minus the removed indexes, in order, byte for byte; each
  removed record is the line it says; no record is over the cap; the text is 250 to 1,200 words with FK below 7.
  The writer also stops if its removed words differ from the report's.
- **Not in it:** passages that are not usable at 10%, and the glossary. Ingestion into the `content` context's
  `Source` is the next step (ADR-0008 decision 3 names the fields; `original_text` and `text` are lists here
  and a join with newlines there).

## Limits

- One labeller, who also wrote the lists and the rules. The census and the samples are a second reading by the
  same person; the recall reading is a judgement of what counts as frame. The strict and the lenient columns
  bracket the main one: closings that recap the lesson or ask the reader to practise are the borderline.
- The recall sample is a fresh draw under frozen rules, but the lists were built from this corpus, so the figures
  describe this corpus and not new VOA text. 120 passages give intervals about 20 points wide.
- The sample was drawn before the length-window fix. None of the 3 passages that the fix moved was in it; the one
  that entered was read as a census (unclean) and counted that way.
- Recall stops here: the 90% target was withdrawn. What is left unlisted is mostly closings, teasers, blurbs and
  practice prompts in *Everyday Grammar*, *Ask a Teacher* and *Words and Their Stories*; the families are in
  [voa-trim-recall.md](voa-trim-recall.md).
