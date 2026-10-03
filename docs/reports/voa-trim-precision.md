# How often are the boilerplate lists wrong?

ADR-0008 lets a trim delete whole lines, and a wrong deletion is invisible later: the passage reads fine, it is
only missing a sentence somebody wrote. So before any trim runs, this report measures how often the lists
that decide what is frame remove something that is not. Read-only on `~/sonari-data`; nothing was trimmed;
the parser, the thresholds and the Flesch-Kincaid formula are untouched. Every line that was read is in
[voa-trim-precision-labels.tsv](voa-trim-precision-labels.tsv) with its label, so each can be checked.

## Result

**No line was wrong.** Among the 1,334 lines a 5% cut would remove, none is content or a content sentence
joined to a sign-off (all 271 distinct texts read). Among 450 lines and texts drawn across the whole
corpus, none either. The error rate of the lists is below 1.2% per line at 95% confidence on the corpus-wide
sample, and 0 on the population that a trim would touch. That is under the 2% at which the work would stop.

| Set | What was read | Wrong | Rate (95% interval, exact) |
|---|---|---|---|
| A | every distinct text among the 1,334 lines a 5% cut removes (271 texts) | 0 | 0 of 1,334 lines (a census) |
| A | random sample of those lines, proportional by length: 248 of up to 10 words, 52 of 11-20, the one line above 20 | 0 | 0 of 301: 0 to 1.2% |
| B | random sample of every line the lists remove in the corpus (68,257), proportional by length: 254, 38, 8 | 0 | 0 of 300: 0 to 1.2% |
| C | random sample of the distinct removed texts above 20 words (150 of 852), where content hides | 0 | 0 of 150 texts: 0 to 2.4% |

A passage that needs a trim loses about 2 lines, so at the upper bound of 1.2% per line up to about 2.4% of
trimmed passages could still hold one wrong removal; none was found.

**What this does not say.** It says what the lists remove is frame. It does not say the lists remove all of
the frame: about 4 passages in 10 of those a 5% cut makes usable still hold a frame line the lists miss (see
"What the lists miss"), and that is the next problem, not precision.

## How it was measured

**The rubric, fixed before any line was read.**

- *Correct removal*: the line is broadcast or page frame. A presenter's introduction or sign-off, a
  programme name, a programme's opening or closing, a credit or contact line, a speaker label alone, a stage
  direction, a call to comment or a question put to the reader as part of one.
- *Real content*: the line says something that belongs to what the passage is about, an argument, a story, a
  dialogue, a speech. Removing it deletes a sentence somebody wrote as part of the text.
- *Joined*: a line that is a sign-off and also a sentence of content. The lists cannot produce one on purpose,
  because a line goes only when every one of its sentences is listed; it would take a listed sentence that is
  really content.

Each line was read with the line before and after it from the same passage.

**Populations and samples.** All draws use `random.Random(20261003)` on populations sorted by (URL, line
index), so they can be re-drawn.

- *A*, the population a trim would touch: the 1,334 lines removed from the 782 passages that pass every filter
  at a 5% cut (FK below 7, 250 to 1,200 words, licence, not a copy; 710 of them need a trim). The sample is
  stratified by length (up to 10 words: 1,100 lines; 11-20: 233; above 20: 1) with proportional allocation by
  largest remainder for 300, plus the single line above 20 words. Because the population has only 271
  distinct texts, the other 147 texts were read too, which makes it a census. (The generated report counts 784
  passages at 5%; the 2 more come from the length window now applying after the cut. The sample was drawn
  before that.)
- *B*, the corpus: all 68,257 lines (up to 150 words) for which `classify` says the whole line is frame, in the
  19,918 passages; 3,531 distinct texts. Same stratification: 57,689 lines of up to 10 words, 8,745 of 11-20,
  1,823 above 20; sample 254, 38, 8.
- *C*, the stratum where a wrong line is most likely: 852 distinct texts of more than 20 words, 150 drawn.

**The labeller** is one person, who also wrote the lists. The lists were built before the sample was drawn,
from sentences found in at least 3 passages, and every one of the 565 sentences and 174 staff names was
read when it went in. The sample is the second reading, not the first.

## Why the lists are right where the rules were not

The rules of PR #32 were patterns over a line. Four patterns, not three, produced the errors:

| Rule | Error | Example it removed |
|---|---|---|
| presenter: `I'm` or `This is` followed by any capitalised word, then anything | the rest of the line is deleted with the sign-off | "I'm Vietnamese and I live in Hanoi...", "This is Xie Xiaoyan." (introducing a speaker in a newscast), "This is Gene Autry, the singing cowboy, singing..." |
| programme: a set of phrases found anywhere in a line of 30 words or fewer | any sentence that names the programme or the service goes | "But, the majority of the VOA Learning English audience lives in places where...", "My deadline for Words and Their Stories is every Thursday...", "He has worked on the Voice of America for ten years." |
| script: any "Name:" line, any parenthesis | a speaker label or a stage note inside the content goes | "RONALD REAGAN:", "Journalist:", "Doctor:", "(At the mailbox)" in a lesson dialogue, "(The American Dialect Society also chose "Y2K" as its Word of the Year...)" |
| label before speech, then the rules on what follows | the speech goes with the label | "DOUG JOHNSON: I'm Vietnamese and I think English is hard." |

The lists have none of these shapes: a line goes only when every sentence is on a list, a name is a slot
only if it is on the staff list, and a label in front of anything else keeps the line whole. The negative
cases of ADR-0008 are tests (`test_corpus_negative_cases.py`, each in both apostrophe forms), and so is the
shape of the data (`test_corpus_frames.py`).

**The old rules, measured the same way.** The old and the new rules agree on 67,930 lines. Only the old
rules remove 5,626 (7.6% of their 73,556 removals); only the new ones remove 327. A seeded sample of 150 of the
5,626:

| What the line is | Count | Meaning |
|---|---|---|
| frame the lists do not cover | 119 | recall the new rules lose: 35 stage directions or cues with a title such as `(MUSIC: "Let's Go Get Stoned")`, 32 calls to comment with a question about the story, 33 credits with names that are not on the staff list, 19 sign-offs and promos |
| a sign-off joined to a sentence of content | 24 | the old rules deleted a topic sentence: "I'm Steve Ember. Today we tell about developments in pain control." |
| content | 7 | "This is Gene Autry...", "RONALD REAGAN:", "This is Xie Xiaoyan.", three parenthetical notes that carry text of the passage, "((laughter))" |

By that sample the old rules removed about 1,160 lines (15% to 28% of 5,626, so 840 to 1,560) they should not
have, 1.6% of their removals (1.1% to 2.1%). That is near the 2% line, and it is a corpus-wide figure: on the
long lines the 85-line reading found 6 of 85. The old rules were not far from acceptable on average; they were
wrong where it is hardest to see.

## What the lists miss

Precision was bought with recall. The check that the report always printed ("short paragraphs repeated most
that no rule catches") still shows only headings, because it counts repeated lines, and the missed frame is
one-off. A seeded sample of 60 of the 782 usable passages, reading every short line that looks like frame
and is still in the text: **23 passages (38%; 27% to 51%) still hold at least one frame line**, so about
480 of the 784 (380 to 570) are mechanically usable and also free of such lines. What is left, by the 119
frame lines above and the 23 passages:

- stage directions and cues with a title, `(MUSIC: "...")`, `((CUT 3: ...))`, `((TAPE: ...))`, `(SOUND: ...)`;
- calls to comment that put a question about the story first, and variants of "Write to us in the Comments
  Section" with other words ("Tell us what you think, write us in the comment section below.");
- credits with names that are not on the staff list, or with two names ("Jill Robbins and Anna Matteo wrote
  this lesson for Learning English.");
- greetings and closings that differ by a word ("Hello and welcome to another Words and Their Stories.").

None of these is a reason to loosen a rule. Each family needs the evidence of ADR-0008 section 5: its matches
listed, read, and tested against the negative cases.

## What would fix it, and what it means

- The precision gate passes: no wrong line in 1,334 and in 450, interval below 1.2% on the sample. A trim with
  these lists would not delete content in this corpus, as far as one reader can tell.
- The recall gap should be closed before the 784 is used: otherwise a passage that "reads fine" still opens
  with "Hello and welcome to..." or ends with a question to the commenters. The four families above, in that
  order of count, each as a closed list or a closed grammar with its own reading.
- Re-measure after every change to the lists: re-draw A and B with the seeds above and read the new lines
  (the TSV shows what has been read). The sampling code was a one-off script and is not committed; making it a
  `make` target is in the backlog.
- Limits: one labeller, who wrote the lists; the lists were drawn from this corpus, so these figures are about
  this corpus and not about new VOA text; the sample cannot see a correct sentence removed in the wrong
  context (a listed sign-off in the middle of a quotation) beyond what the neighbouring lines showed.
