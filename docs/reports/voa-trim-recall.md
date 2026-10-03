# How much frame do the boilerplate lists still miss?

[voa-trim-precision.md](voa-trim-precision.md) showed that what the lists remove is frame, and that about 4 in 10
of the passages a 5% cut makes usable still held a frame line the lists miss. This report closes part of that
gap and measures what is left, the same way as before: a seeded sample of the usable set, read in full.
Read-only on `~/sonari-data`; nothing was trimmed; the parser, the thresholds and the Flesch-Kincaid formula
are untouched. Every passage and line that was read is in
[voa-trim-recall-labels.tsv](voa-trim-recall-labels.tsv), so each label can be checked.

## Result

**The target is not met.** The aim was more than 90% of the usable passages free of an uncovered frame line.
At a 5% cut it is 68% (58% to 78%), up from 52% (41% to 63%). Recall improved a lot; it did not reach the
target, and the passages that remain usable are fewer (678, not 784) because the lists now see frame that
earlier counted as text.

| Cut at most | Usable before | Free of frame, before | Usable after | Free of frame, after | Usable and clean, before → after |
|---|---|---|---|---|---|
| 2% of the words | 484 | 52% (38% to 68%) | 368 | 75% (60% to 88%) | 254 → 276 |
| 5% | 784 | 52% (41% to 63%) | 678 | 68% (58% to 78%) | 407 → 462 |
| 10% | 1,153 | 56% (47% to 66%) | 1,123 | 71% (62% to 79%) | 650 → 793 |

"Usable" is the count of the filter of `voa-corpus.md` at that cap (FK below 7, 250 to 1,200 words after the
cut, licence, not a copy). "Free of frame" is the share of the sample with no line left that is frame, and
"usable and clean" is that share times the usable count. Intervals are 95% bootstrap intervals (4,000 draws,
seed 1) over the three strata below. The 55 passages usable as is (no cut at all, 7 of them lesson or fiction
passages) sit inside the 2% stratum and were not sampled on their own.

Two figures from the previous report change under a full reading. It estimated 38% unclean (23 of 60) and about
480 usable and clean at 5%; the same passages and rules read line by line give 48% and about 407. The first
reading looked only at short lines that matched a keyword pattern, so it missed the long closings and blurbs
that dominate what is left now. The "before" column here is the full reading.

## How it was measured

**The rubric, fixed before any passage was read.** A passage is *unclean* when, after the lines the rules
remove whole are taken out, at least one line is left that is frame: a presenter's opening, closing or teaser,
a programme blurb, a credit, a stage direction or cue, a call to comment or practise, a pointer to a video or
a page of the site, an editor's note, a page header. Lines of content are not counted, nor are headings that
are part of the text ("Closing thoughts" is a heading, and the line after it is counted if it is a teaser).
Every line that the rules leave was read, not only those that look like frame.

**Populations and samples.** The usable set at each cap was taken from the repo's own `blockers()` with the
rules of round one (before) and the final rules (after). Each is stratified by the lowest cap that admits the
passage: usable at 2% (40 drawn), at 2-5% (45) and at 5-10% (35), 120 per set, drawn with
`random.Random(20261003)` (before) and `random.Random(20261005)` (after) from populations sorted by URL. The
two samples are independent draws, not the same passages.

| Stratum | Before: population, unclean of drawn | After: population, unclean of drawn |
|---|---|---|
| usable at 2% | 484, 19 of 40 | 368, 10 of 40 |
| 2-5% | 300, 22 of 45 | 310, 18 of 45 |
| 5-10% | 369, 12 of 35 | 445, 9 of 35 |

The "after" set was read with the rules frozen. No rule was changed to fit a passage in it; the quick wins
found while reading it (below) were left unfixed on purpose so that the code measured is the code committed.

**The labeller** is one person, who also wrote the rules (see Limits).

## What was added

Four groups were listed in advance. Each came with the evidence of ADR-0008 section 5: the matches listed and
read, a shape anchored at both ends, tests for what it must keep, the measured effect.

| Group | What covers it now |
|---|---|
| captions such as `(MUSIC: "...")` | one rule for `(MUSIC|SOUND|CUT|TAPE|ACT|SFX ...: title)` with up to three parentheses; a parenthesis that is text, such as "(Sound familiar?)", stays |
| comment invitations with a separate question sentence | a reader question (ends in `?`, addresses `you`, at most 35 words) inside an invitation line goes with it; a question-only line (two questions or ten words) beside a cut invitation that names a channel goes too, one step along a chain |
| credits with names outside the 174 | 4 names added, a run of names counts as one slot, credit sentences for "wrote / adapted / produced / read" and "was written by", a VITA contact block |
| greetings that differ by one word | an opener rule with a closed lead and a closed set of openers, with the programme title or report topic as a slot (18 titles, 9 topics) |

The rest of the lists grew around them: a glossary-entry rule (a word, a dash and a part-of-speech tag), the
`Broadcast:` date line, and about 190 sentences taken from the corpus, each read when it went in.

**A departure from ADR-0008 section 5.3.** The section asks for the variable part of a rule to be a closed
list. A song title, a topic of a report and what a reader is asked cannot be listed, so most of the 18 rules in
`frames/patterns.tsv` keep closed words at both ends and a bounded open slot between them (at most 100 to 140
characters, never crossing a sentence or a line); the widest is the definition after the part of speech in a
glossary entry. The ADR records this; whether to keep it is a decision for the maintainer. The neighbour rule
also looks at the next line, which the ADR did not foresee, though it still removes whole lines only.

## Precision, measured again

Round two removes 74,965 lines against 68,257 for round one: 6,708 more, none fewer (programme 1,935,
glossary 1,923, call to comment 1,878, script 737, presenter 235). The gate of 2% still applies to what they
added.

| Set | What was read | Wrong |
|---|---|---|
| `added-sample-1` | 355 of the 6,623 lines added at the time (`random.Random(20261004)`; glossary 90, comment 90, programme 90, script 45, presenter 40); all 355 are still removed by the final rules | 0 |
| `added-sample-2` | 200 of the final 6,708 (`random.Random(20261006)`; 40, 50, 50, 30, 30) | 0 |
| `neighbour-census` | all 57 lines the first version of the neighbour rule removed | 2 content lines |
| `gain-census-1` | all 84 lines the opener and VITA rules added in one step, and the 4 lines tightening dropped | 0 |
| `gain-census-2` | the 5 lines added after that | 0 |

None was wrong among 555 random added lines: the upper 95% bound is 0.66% per added line (the draws are
stratified by kind, so the bound is approximate). The census found the two errors that matter: "What can you
do?" and "How might you negotiate a lower price?", exercise questions beside an instruction, removed because
they stood next to an invitation. The rule now needs a neighbour that names a channel, two questions or ten
words, and a chain of one step; both lines stay, with tests (`test_corpus_patterns.py`). One correct line also
stopped being removed. The three negative cases of ADR-0008 still pass in both apostrophe forms.

## What is left

The 37 unclean passages of the "after" sample hold 58 uncovered lines. By family, with the number of
passages that hold one:

| Family | Lines | Passages | Example |
|---|---|---|---|
| A. closings and teasers in plain prose | 22 | 19 | "That's our program for this week. Join us again soon for Part 2."; "Next week on the Health Report: advice from experts..."; "We leave you with Frank Sinatra, singing Autumn Leaves." |
| B. programme blurbs and openers with other wording | 12 | 12 | "Each week we explore the stories behind common American words and expressions."; "I'm Rich Kleinfeldt with expressions made using the word hold." |
| C. practice or discussion prompts, mostly without a channel word | 9 | 8 | "Practice what you learned today!"; "Give the Pomodoro technique a try, and let us know how it works for you." |
| D. editor or series notes, cross-references, page headers | 7 | 6 | "Editor's note: This is the third episode of a four-part series..."; "Read and listen to the article. Then open the activities..." |
| E. pointers to a video, a song or a page | 8 | 5 | "Here is a video explaining the difference between the simple past and the past perfect."; "The song at the end is Marvin Gaye singing..." |

Of the 37 passages, 26 have lines from one family only (A 11, B 7, C 4, D 3, E 1) and 11 from two or more.

**Is it a long tail of one-offs, or a group worth covering?** Both, and the split is useful. Inside a family
the lines are one-offs: the 22 lines of A have 22 different wordings. But they share a grammar (a verb of
closing or promising plus the name of the series or of a lesson to come), and three families carry most of the
tail: A, B and C are 43 of the 58 lines. A touches 19 of the 37 passages, half of them. Weighted to the 5% set,
the share of passages with a frame line left would go from 32% to about 21% if A were covered, 17% with B, and
11% with C: **about 89% clean, close to the 90% target, with three families of open-wording prose**. Those
figures are in-sample (the families were drawn from these lines), so they are an upper bound for what rules
written from them would do on other passages.

A, B and C are prose that reads like content, which is why they were left: "Future lessons will explore gift
giving in greater detail." and "We will look at those in another episode of Everyday Grammar." are frame at the
end of a lesson and content in the middle of one. A rule for them needs closed anchors, such as the name of a
series of the corpus, and a reading as careful as the neighbour rule's, which cost two errors the first time.
D and E are smaller and more regular (a header, a note, "Here is a video...").

**Quick wins, left unfixed.** Four passages of the sample (3, 17, 24 and 45) are unclean only because of one
of three small things: curly quotes around a title break the `<prog>` slot (“Words and Their Stories” does not
normalise); the page header "Read and listen to the article..."; and "(The story continues next week)".
Applied in a scratch copy they add 46 lines to the corpus-wide removal set and move the sample from 68% to
about 73% clean at 5%. They are in the backlog.

**A screen instead of more rules.** A regular expression that blocks a passage when a line the lists leave
holds a channel, a programme word or a closing phrase gave about 83% to 87% free of frame, at the price of
blocking more than a third of the passages. It was tried on the "before" sample only, the passages the lists
were tuned on, so even that figure is optimistic, and it was not adopted. It is an option if the usable count
matters less than the cleanliness; a passage that is blocked would still need a person to read it.

## Limits

- One labeller, who also wrote the rules and the lists and read the sentences that went in. The precision
  samples are a second reading by the same person; the recall reading is a judgement of what counts as frame.
  A second reader could shift both. The same holds for the labels of the previous report,
  [voa-trim-precision-labels.tsv](voa-trim-precision-labels.tsv).
- The lists were built from this corpus, and the uncovered lines of the "before" sample were among what went
  into them, so that sample would flatter the final rules; it is not used for the "after" figure, which is a
  fresh draw under frozen rules. The figures describe this
  corpus, not new VOA text.
- The intervals come from 120 passages per set, which is why they are 10 points wide. The two sets are
  independent draws, so the difference between them has a wider interval than either.
- Only whole lines that are all frame count as removed; a frame sentence glued to content on one line stays in
  the text and blocks the passage as is ("kept" words in `voa-corpus.md`), so a passage with such a line is not
  usable and is not in these samples either way.
- The sampling and the reading helpers were one-off scripts and are not committed; `make voa-precision` is in
  the backlog.
