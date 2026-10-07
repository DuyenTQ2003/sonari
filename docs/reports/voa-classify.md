# What kind of text the 724 passages are

> **The safety numbers below are the first run.** [voa-safety-stems.md](voa-safety-stems.md) narrows the stems and
> splits the disaster rule: usable with no flag is now **264** by the default rule (strict 303, loose 184), not 240.
> The type counts, the validation of the types and the per-unit tags are unchanged.

The "usable" count of [voa-corpus.md](voa-corpus.md) measures length, difficulty and boilerplate. It does not
say whether a passage can carry a lesson. This report classifies the 724 trimmed passages by **type** and by
**topic safety** and counts what is left. Measurement only: no trimming, no schema, no generation, no LLM call
in the classifier, no corpus written, and the parser, thresholds, trim rules and ADRs are untouched.

```bash
make voa-classify                      # the counts below (a few seconds; read only on ~/sonari-trimmed)
make voa-classify ARGS=--tsv           # one line per passage: id, type, rule, flags, units, as-is, title
make voa-classify ARGS="--sample 50"   # the seeded sample, shuffled, with no tag on it
make voa-classify-validate             # scores docs/reports/voa-classify-labels.tsv
```

Input: `trimmed.jsonl`, 724 passages, rules `voa-trim/163aae96e072`. Code: `tools/voa_corpus/classify.py` (the
rules), `classify_report.py`, `classify_validate.py`, the stems in `safety.tsv`. 294 lines of code in the three
modules; the tests (`test_corpus_classify.py`) cover the classification logic only.

## Result

- **370 of the 724 (51%) are a single-topic explainer or a news item.** 322 (44.5%) teach English, and 32 more
  are a story, a newscast, a magazine, a dialogue script or a reader's letter.
- **240 (33%) are an explainer or a news item with no safety flag. That number, not 724, is what the reading
  path can use today.** It moves with how strictly a flag is set: 287 if only the title and the lead count, 144
  if one mention in the body does. The flags over-fire (below), so 240 is likely low; about 280 to 340 if the
  false-alarm rate seen in the sample held.
- Of the 48 passages usable as they are (nothing cut), 24 are an explainer or a news item and 15 also have no flag.
- **Sport is the thinnest unit**, 13 passages with no flag by the default rule (8 to 18 across the three rules).
  Music and Animals follow with 18. Every unit stays above the proposal's 6 even if one mention in the body
  counts as a flag (Sport 8), provided the keyword tags are right (they were not validated).
- The classifier is good where that number needs it and weak at a boundary that does not matter to it. In the
  sample of 50 it was wrong on 2 about whether a text is an explainer or news item *at all* (corpus-weighted
  5.6%, 95% interval 1.5% to 15.5%), and on 12 about the exact type, 10 of those 12 only swapping explainer
  and news item.
- The flags have no miss in the sample and 8 false alarms in 15 flagged explainer/news passages. Sample sizes
  are small; read the intervals, not the point values.

## 1. Type

Seven categories from the proposal and one the data demanded. The rules run in this order and the first that
fits decides; `--tsv` prints which rule decided each passage.

| type | passages | share | what decides it |
|---|---|---|---|
| explainer | 187 | 25.8% | nothing else fits: describes what something is, how it works or what to do |
| news item | 183 | 25.3% | reported speech: 0.5 attribution words (said, told, according to...) per 100 words, 0.25 in *As It Is* and *What's Trending Today?*, with little "you" and under three section headings |
| english_teaching | 322 | 44.5% | a lesson programme (*Everyday Grammar* 182, *Words and Their Stories* 98, *Ask a Teacher* 19, *Early Literacy* 2, one *Let's Learn English* review), a lesson title or header (6 with no programme), or an *Education* article titled about English itself (14) |
| advice_column | 15 | 2.1% | **new.** A reader's letter: the title starts "Woman, 26, Vietnam:" or "Man, 21, Pakistan:" |
| dialogue_script | 9 | 1.2% | at least 6 lines with a speaker label ("Anna: ...") and half or more of all lines |
| fiction | 4 | 0.6% | programme *American Stories*, or a title with "Presents '"; includes the poem read aloud |
| magazine | 3 | 0.4% | the title starts "American Mosaic" or holds two semicolons |
| newscast | 1 | 0.1% | the title starts "VOA English Newscast" |

- **The programme field is an input, not only the title.** The brief said title patterns and body structure; 630
  of the 724 records carry a `program`, and it is the strongest signal there is (the 98 *Words and Their
  Stories* and 182 *Everyday Grammar* passages are one rule). 94 passages have none and are decided by title and
  structure. `filters.LESSONS_OR_FICTION` already uses the same field.
- `advice_column` was added because 15 passages are a reader's letter asking for advice, neither an explainer
  nor news ("My husband is cheating on me"). The three I read hold only the letter, and none of the eight
  units is about personal relationships; yet 7 of the 15 are keyword-tagged to *Study and work*, which shows
  how crude the unit tags are.
- **English-teaching also covers advice on learning English** (14 passages: "Four Ways to Find an English
  Speaking Partner"). It is about English, so it cannot carry a topic unit; a reader may disagree.
- 311 passages of the 724 sit in English-lesson or fiction programmes (voa-trim-corpus.md); this table puts 322
  and 4 there because it also counts titles and the *Education* articles.
- Only 3 passages are a magazine of several segments by the classifier's count, all by title. Whether the
  trim leaves others whose segments are unrelated was not measured.

## 2. Topic safety

A flag is a lead for a reader, never a filter: nothing is deleted. A category is flagged when one of its stems
(`safety.tsv`) is in the **title or the lead paragraph, or occurs 3 or more times in the body**.

| category | flagged |
|---|---|
| war | 51 |
| politics | 69 |
| disaster | 6 |
| disease | 28 |
| crime | 78 |
| death | 58 |
| **any** | **206** |

How strictly a flag is set moves the count of passages that are an explainer or news item with no flag:

| flag rule | flagged | usable |
|---|---|---|
| strict: a stem in the title or lead only | 112 | 287 |
| **default: or 3 or more in the body** | **206** | **240** |
| loose: any hit in the body | 389 | 144 |

- The stems were fixed after reading which words fired on all 724: `sentenc` matched every grammar sentence
  (790 times), `trump` the instrument, `aids` the verb. They are now `sentenced|sentencing`, `trump\b` and a
  case-sensitive `AIDS`.
- Among the explainers 47 of 187 (25%) are flagged; among news items 83 of 183 (45%).
- **Tornado Season!, one of your two explainers, is flagged `disaster`.** By the list it should be; whether a
  weather explainer is unsafe for a student is the decision the flag leaves to a reader.

## 3. The intersection

| step | passages |
|---|---|
| in the trimmed corpus (all pass the level 4 filter at a cut of at most 5%, by construction) | 724 |
| single-topic explainer or news item | 370 |
| and no safety flag, default rule | **240** |
| the same under the strict / loose flag rule | 287 / 144 |
| of those 240, tagged to at least one of the eight units by keyword | 154 |
| usable as they are, nothing cut, with type and no flag | 15 (of 48) |

Not applied here: `voa-trim-corpus.md` found about 43% of the 724 still hold a frame line the lists miss (57%
free, interval 46% to 67%). That share was concentrated in *Everyday Grammar*, *Ask a Teacher* and *Words and
Their Stories*, so the explainers and news items are probably cleaner than 57%. This report did not measure it.
P50 still reads each chosen passage.

## 4. Per unit

A passage can match several units (crude keywords on the title and lead, `units.tsv`, the same as the earlier
reports, which these counts reproduce: 52, 126, 63, 62, 42, 47, 48 and 28 tagged), so the rows do not add up.
352 passages match no unit.

| unit | tagged | explainer or news | no flag: strict | **default** | loose |
|---|---|---|---|---|---|
| Healthy habits | 52 | 41 | 33 | **27** | 19 |
| Study and work | 126 | 61 | 52 | **36** | 26 |
| Food and eating | 63 | 38 | 32 | **27** | 20 |
| Technology | 62 | 40 | 37 | **36** | 28 |
| Animals | 42 | 24 | 19 | **18** | 10 |
| Music | 47 | 29 | 22 | **18** | 9 |
| Nature and places | 48 | 41 | 32 | **25** | 10 |
| Sport | 28 | 21 | 18 | **13** | 8 |

- **Sport** is thinnest under all three rules. *Study and work* loses the most to the type filter: 56 of its 126
  tagged passages teach English.
- These counts are where to look, not how many passages exist: the tags were not validated, and a keyword like
  "student" or "eat" tags passages that are not about the unit.

## 5. How far the classifier can be trusted

**Method.** 50 passages drawn with seed 20261007, stratified by the type the classifier gave (13 explainer,
13 news item, 10 english_teaching, 4 dialogue_script, 3 each advice_column, fiction and magazine, 1 newscast;
the most reads go where errors are likely). Each was **read in full and labelled before its tag was looked
at** (`--sample` prints no tag). The labels, with a note each, are in `voa-classify-labels.tsv`. A passage is
flagged by hand for a category when it is the main subject or a distinct section of its own (about a tenth of
the text); a passing mention is not.

**What this does not prove.**

- **One labeller, and it is the assistant that wrote the classifier,** not you and not a second reader. Please
  read the notes of the 21 passages the classifier got wrong in the labels file and overrule any you disagree
  with; `make voa-classify-validate` rescores at once.
- **Not held out.** The rules were written after reading the titles and the per-programme statistics of all 724
  passages, so the sample comes from the data the rules were shaped on. The error rates are optimistic. No rule
  was changed after the scores were seen; only the scoring code was.
- The explainer/news boundary is soft for the labeller too: 6 of my 26 explainer and news labels carry a
  "borderline" note, and I changed one label (the harmonica feature) while reading, to keep to my own rule (news
  = something that happened or someone's recent activity; explainer = what a thing is, how it works, what to
  do). Treat that boundary as unresolved, not as an error rate.

**Results.** 95% interval is a Jeffreys posterior per stratum, weighted by the stratum's share of the 724, so
a stratum with no error still contributes doubt.

| measure | errors in the sample | corpus-weighted median (95% interval) |
|---|---|---|
| exact type (8 categories) | 12 of 50 | 24.4% (15.1% to 35.6%) |
| **usable type** (explainer or news item, or not) | **2 of 50** | **5.6% (1.5% to 15.5%)** |
| any safety flag, all types | 11 of 50 | 30.7% (17.7% to 46.3%) |
| any safety flag, explainer and news only | 8 of 26 | 31.6% (16.8% to 49.7%) |

By predicted type: explainer 7 of 13 wrong on exact type (1 on usable type), news item 4 of 13 (0), magazine 1
of 3 (1), and english_teaching 10 of 10, dialogue_script 4 of 4, advice_column 3 of 3, fiction 3 of 3 and
newscast 1 of 1 right.

**Where it misclassifies.**

1. **Explainer against news item (10 of the 12 type misses, both directions).** Six news items tagged
   explainer (a prom-dress debate, a NASA test, a blues CD, a school, a frog-sniffing dog, a World Series
   preview) and four explainers tagged news item (parsley, harmonicas for lung disease, why people join the
   military, boatbuilding). The cut at 0.5 attribution words per 100 is a soft line; a feature written with
   quotes reads as news. It does not change the headline, which counts both.
2. **The "American Mosaic:" title.** 1 of 3 magazines ("42" and Jackie Robinson) holds one topic in the stored
   text, so the title rule over-fires. This is one of the two errors on usable type.
3. **An English lesson with no programme signal.** "Some New Words for VOA's Word Book", an April Fools piece
   that introduces three slang words, is tagged explainer. The other usable-type error.
4. **Safety flags over-fire: 11 false alarms in 50, none missed.** In the 26 explainer and news passages the
   classifier flagged 15 and I flagged 7 (all 7 among its 15); precision 7 of 15 (interval 25% to 70%). 11
   unflagged passages is too few to rule out a miss, so "the flags are safe" is not shown either. The false
   alarms come from three causes:
   - generic stems: `president` (a World Series preview, Memphis, a grammar lesson), `government` (matatu art,
     a STEM programme), `politic` (a doctor and one Greek politician), `violen` (a violent wind, "explosive"
     idioms), `attack` (cheetahs attacked by lions);
   - one anecdote counted again and again: a veteran's D-Day story gives 5 war words in a 91-year-old's flying
     lesson; "politician" 4 times in one story; "deadly fungus killed" in a dog-and-frog story;
   - a real topic that is only a short part: Memphis, where the King murder is 2 of 49 lines (7% of the words).

   Ideas for each are in `docs/backlog.md`; none is coded here.

## 6. Dialogue scripts

9.
