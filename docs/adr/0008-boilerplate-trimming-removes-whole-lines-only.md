# ADR-0008: Boilerplate trimming removes whole lines and nothing else

- Status: Accepted
- Date: 2026-10-03

## Context

`docs/reports/voa-corpus.md` (parser and rules at `27effcd`) found that 2,472 passages
pass the level 4 length and grade filter and 102 of them carry no editorial boilerplate:
96% fail on the radio script's frame alone (presenter lines, programme names,
"VOICE ONE:" labels, calls to comment). Only 98 passages are usable as is (68 once
English-lesson and fiction programmes are set aside). The report puts the count at 1,165
if up to 5% of a passage's words may be cut. That is the largest lever left, by a factor
of about 12, and ADR-0006 says nothing about it: cutting is not generating, but the
stored text would no longer be exactly what VOA published.

Two facts shape the decision:

- **The report's 1,165 is not what whole-line removal delivers.** The report counts the
  words of a speaker label as cuttable even when the line goes on with speech
  ("MIKE LIZOTTE: If you want that bulb to survive..."). A whole line cannot be removed
  without losing the speech, so 159 of the 1,165 only work if the label is stripped
  from the line. Whole lines only: **1,006** (table below).
- **The rules were written to count, not to delete.** In the report a false positive
  moves a count by a little. In a trim it silently deletes passage content from a text
  that a learner is taught from. Read at `27effcd`, the rules fail the negative cases
  below. A reading of 85 removed lines at the 5% cap (all 45 over 20 words and 40
  random lines of 11 to 20) found 4 that are plainly passage content and 2 more that
  glue a content sentence to a sign-off. It is not a precision estimate: lines of 10
  words or fewer, 80% of the removed lines, were not read. It shows the rules are not
  ready to delete with.

## Decision

1. **Trimming removes whole lines and does nothing else.** A *line* is a body paragraph
   as `voa_inventory.parse` returns it (a `<p>`, or a bare-text line). A trim never
   edits a word, a space or a mark inside a kept line, never reorders, never inserts
   (no placeholder, no joined lines). A line that carries any passage content is kept
   whole, speaker label included; so is a line that glues a sign-off to a sentence of
   content. Page furniture ("Share", "Print", "No media source currently available") is
   removed and recorded like any line, but does not count toward the cap: it is layout,
   not passage, and the report never counted it.

   *Why this does not conflict with ADR-0006.* ADR-0006 bans generated English: text
   an author or a model wrote. A trim selects a subsequence of lines of the original.
   Every kept line is byte-identical to VOA's; nothing is authored, rewritten, reordered
   or added. This is checkable: the kept lines must equal the original lines minus the
   removed indexes, and the write-time validator and a property test enforce it.

2. **The cap is 5% of the passage's words**, counted as the report counts them
   (`words`, as extracted), over editorial lines only. The length window (250-1,200
   words) and the grade ceiling (Flesch-Kincaid below 7) are applied to the trimmed
   text. They do not change, and the grade does not move (it is already measured
   without these lines). Length does for 1 passage at 5%, which falls under 250 words.
   Changing the cap is a superseding ADR with the table below regenerated.

   Passages usable for level 4 (FK below 7, 250-1,200 words, VOA-staff licence, copies
   removed), at `27effcd`, before any rule is tightened:

   | Cap | Report's counting | Whole lines only | After length recheck |
   |---|---|---|---|
   | as is | 98 | 98 | 98 |
   | 2% | 572 | 535 | 535 |
   | **5%** | **1,165** | **1,006** | **1,005** |
   | 10% | 1,839 | 1,596 | 1,594 |
   | none | 1,986 | 1,715 | 1,702 |

   | Cap | Passages needing a trim | Lines removed per passage | Removed share of words | Removed lines over 20 words |
   |---|---|---|---|---|
   | 2% | 437 | median 1, p90 2 | median 0.7%, p90 1.8% | 1 |
   | 5% | 908 | median 2, p90 3 | median 2.1%, p90 4.4% | 45 |
   | 10% | 1,498 | median 2, p90 5 | median 3.9%, p90 7.9% | 270 |

   Why 5%. At 2% the yield is about half (535). From 5% to 10% it gains 590 passages, but
   they need 4.9 lines each against 2.2 at 5% (122 passages lose six or more), and longer
   ones, and long lines are where content hid in the reading above (all four
   plain-content lines were 19-22 words). At 5% the median passage loses two lines and
   2% of its words.

3. **Provenance.** Ingestion stores, on the `Source` document in the `content`
   database (ADR-0001; PLAN 5.1; written by the P40 and P50 prompts):

   | Field | Holds |
   |---|---|
   | `original_text` | the lines as the parser returned them, untouched |
   | `text` | what everything else reads (learnables, exercises, TTS): the original minus the removed lines |
   | `trim.rules_version` | the version of the trim rules that ran |
   | `trim.removed` | `[{index, kind, rule, text}]`: the 0-based line index in `original_text`, the rule's kind and id, the line itself |

   Any trim can be audited by reading `trim.removed`, and undone by taking
   `original_text`. A passage that was not trimmed has `removed: []`. Example sentences,
   questions and the passage audio come from `text`, never from a removed line. One
   function does the trimming, and both `make voa-corpus` and ingestion call it, so the
   report counts what ingestion would produce.

4. **What a trim must never remove.** These are standing tests in
   `tools/voa_corpus/tests/`; a rule that fails one does not land. "Today" is the
   classifier at `27effcd` (`boilerplate.tsv`): where it says *removed*, the line would
   be deleted whole.

   | Case | Line | Today |
   |---|---|---|
   | Speech behind a speaker label | `MIKE LIZOTTE: "If you want that bulb to survive, you would need to dig it out."` | kept (label counted, not removed) |
   | | `DOUG JOHNSON: I'm Vietnamese and I think English is hard.` | removed (presenter) |
   | | `JOHN KERRY: "We want to hear from you, the voters, before we decide."` | removed (call to action) |
   | An ordinary sentence that starts like a sign-off | `I am Vietnamese and I live in Hanoi with my family.` | kept |
   | | `I'm Vietnamese and I live in Hanoi with my family.` (also with `’`) | removed (presenter) |
   | | `This is Vietnam and the weather is hot all year.` | removed (presenter) |
   | A short sentence that mentions the Voice of America | `She explained that the voice of America is a news service.` | kept |
   | | `He has worked on the Voice of America for ten years.` | removed (programme) |
   | | `She said the story was first broadcast on the Voice of America in 1962.` | removed (programme) |
   | A sentence that names the programme | `But, the majority of the VOA Learning English audience lives in places where English is not the main language.` | removed (programme) |
   | | `My deadline for Words and Their Stories is every Thursday. When I meet my deadline, I can relax and enjoy my Friday.` | removed (programme) |

   The last two lines are VOA's own text from the corpus. PR #32's tests pin only the
   uncontracted `I am` and the sentence where the Voice of America is the subject, so the
   contracted forms and the "on/by the Voice of America" mentions passed unnoticed.
   A label followed by a sign-off ("VOICE ONE: I'm Bryan Lynn.") is still removable: the
   rest of the line is itself a sign-off. A label followed by anything else keeps the line.

5. **How a trim rule is added or changed.** None of the rules in `boilerplate.tsv` is
   grandfathered. That file stays the measurement set the report has used; the
   implementation of this ADR qualifies each rule for trimming under this section. A rule
   lands only with all of these in the PR:

   1. **Its matches listed.** Every distinct normalised line it removes in the corpus,
      with the number of passages; above 100 distinct lines, a random 100 spread over the
      years. In the PR body or a committed file under `docs/reports/`.
   2. **A precision reading** of that list by the maintainer: zero lines that carry
      passage content. With 100 distinct lines read and none wrong, the 95% upper bound
      on the false-positive rate is about 3% (rule of three). Fewer than 100: read all.
   3. **Shape.** It matches the whole line, anchored at both ends. Variable parts
      (presenter names, programme and report titles) come from a closed list taken from
      the corpus, not from a capitalised-word or any-substring pattern. All three
      misfires were open patterns: a prefix, a prefix after a stripped label, a substring.
   4. **Negative tests.** The standing cases in section 4, plus the nearest
      content-bearing line the rule could be confused with (from the corpus when one
      exists), in every spelling the corpus uses (`'` and `’`, contracted or not).
   5. **Its effect.** The number of passages it unlocks at the default cap, from the
      sensitivity table with and without it. A rule that unlocks none is not added.
   6. **A version bump** of `trim.rules_version`. Ingested passages keep the version they
      were trimmed with. Re-trimming one is a separate step, with the removed lines
      before and after read.

## Consequences

- The ceiling at 5% is about 1,006 passages, not 1,165, and falls once the rules are
  tightened (measured on 2026-10-03 with the closed lists: 784, `docs/reports/voa-corpus.md`). The implementation reports the real figure, and the table above is then
  regenerated by `make voa-corpus` instead of quoted (its 2% and 10% rows and the
  whole-line column came from a one-off script that reuses the report's code; at 0%, 5%
  and no cap its report-counting column reproduces the report's 98, 1,165 and 1,986).
- The stored text is VOA text minus its broadcast frame, not VOA's text. `trim.removed`
  being non-empty marks it, and P50 still reads every chosen passage in full: a trim
  does not replace reading.
- 271 of the 1,986 candidates (FK below 7, length, licence) keep a speaker label on a
  line with speech and can never be clean under this ADR. They stay out until a later
  ADR permits stripping a label.
- Stricter rules lose recall: some frame lines will be left in, and some passages will
  stay over the cap. This is accepted: a missed sign-off costs one passage, a deleted
  content line costs a lesson nobody notices.
- Each ingested passage stores its text twice, a few KB. Negligible.

## Alternatives rejected

- **Strip speaker labels inside a line.** Worth up to 159 passages at 5% in the report's
  counting. It edits inside a line, which is the line this ADR draws; it can come back
  as a superseding ADR with its own evidence.
- **Cut sentences, not lines.** Removes the glued sign-offs, but every cut then lands
  inside a line, and sentence splitting makes errors that line boundaries do not.
- **Let an LLM clean the text.** Generated English; ADR-0006.
- **No trimming; choose among the 98.** After lesson and fiction programmes 68 remain,
  and the report counts 3 to 22 per unit, where the units proposal wants 6 to be
  comfortable.
- **A cap above 10%, or none.** The passages it adds are the ones whose frame is part of
  the text, and the removed lines grow longer, so the risk grows with them.
- **Trim without storing the original.** Nothing could be audited or undone.
