# VOA text-less pages: what they are

`docs/reports/voa-corpus.md` counts 27,118 article pages with no text and 1,768 with under 100 words
(28,886 of 47,854, 60%) and calls them audio or photo pages. This report checks that by reading a
fixed-seed sample of the cached HTML, then counting what the parser cannot read across the whole
cache. Read-only on `~/sonari-data`; no network, no LLM; the sample is drawn by `SEED = 20261003`.

**Status.** This is the picture before the fix (parser at `62b6669`). The parser now reads the bare text,
see "The fix" below and the before/after table in `voa-corpus.md`. The sample is drawn from the pages'
word counts, which the fix changed, so `make voa-missing` no longer reproduces the draw: to re-run this
report, check out `62b6669`.

## Finding

- **The parser misses real articles.** 942 of the 1,768 pages with 1-99 words (53%) hold an article of
  100 or more words that `voa_inventory.parse` never reads. In the sample it is 9 of 15 (60%, 95%
  interval 36-80%), which implies 1,061 pages (632-1,418). The 942 is the count from the census below.
  They are 5.0% on top of the 18,968 passages, and 12 times the 76 usable as-is passages of the
  earlier report.
- **The 27,118 pages with no text are not that.** 0 of 40 sampled are missed articles: 36 are audio
  pages (90%), 3 are quiz or Word of the Day widgets, 1 is a photo gallery. The census finds 1 page in
  all 27,118 with 100 or more unread words (a 102-word photo essay). The sample alone cannot rule out
  a miss rate up to 8.8% (2,376 pages); the census does, for this failure mechanism (see limits).
- **All of it is one defect.** The article body sits as bare text in `div.wsw` or `div.wordclick`,
  separated by `<br />`, with no `<p>`. 881 of the 942 pages are from 2012-2014.
- **It changes the numbers, not the conclusions.** A throwaway prototype of the fix (not committed)
  makes 34 of the 942 usable as is (76 to about 110) and 97 more usable if boilerplate may be cut.
  Boilerplate and grade level still block most of them.

## Method

1. Pages are the 47,854 article URLs of `index.jsonl`, grouped by the words `parse_page` reads: 0
   words (27,118) or 1-99 words (1,768). URLs are sorted, then `random.Random(20261003)` draws 40 and
   15 (`missing.draw`).
2. Each page was read by hand from its cached HTML (page structure, the longest text nodes, player,
   quiz and caption markup) and given one label. The label and the evidence for it are in
   `voa-missing-labels.tsv`; the command checks that the file still matches the draw.
3. The census counts, for every page, the words in text nodes of `#article-content` that sit outside
   the tags the parser reads (`p`, `h2`, `h3`, `figcaption`), outside player, quiz, share and comment
   boxes, lists, links, forms and scripts, in nodes of 40 or more characters. Unread text of 100 or
   more words on a page the parser read as 0-99 words is a missed article.

## The sample

Hosts are `https://learningenglish.voanews.com`. Labels: `audio` = audio player page with no text,
`widget` = quiz or Word of the Day widget filled in by script, `gallery` = The Day in Photos, `video` =
video lesson, `MISSED` = article the parser did not read. Section index, paywall, error and redirect
pages: none in the sample, and no title among the 27,118 looks like an error page.

| # | group | label | URL |
|---|---|---|---|
| 1 | 0 words | audio | https://learningenglish.voanews.com/a/1978259.html |
| 2 | 0 words | audio | https://learningenglish.voanews.com/a/5990754.html |
| 3 | 0 words | widget | https://learningenglish.voanews.com/a/1935785.html |
| 4 | 0 words | audio | https://learningenglish.voanews.com/a/3344276.html |
| 5 | 0 words | audio | https://learningenglish.voanews.com/a/2267557.html |
| 6 | 0 words | audio | https://learningenglish.voanews.com/a/4839396.html |
| 7 | 0 words | audio | https://learningenglish.voanews.com/a/2915258.html |
| 8 | 0 words | audio | https://learningenglish.voanews.com/a/5098628.html |
| 9 | 0 words | audio | https://learningenglish.voanews.com/a/2216285.html |
| 10 | 0 words | widget | https://learningenglish.voanews.com/a/6320133.html |
| 11 | 0 words | audio | https://learningenglish.voanews.com/a/3772875.html |
| 12 | 0 words | audio | https://learningenglish.voanews.com/a/5010817.html |
| 13 | 0 words | audio | https://learningenglish.voanews.com/a/3010845.html |
| 14 | 0 words | audio | https://learningenglish.voanews.com/a/1979838.html |
| 15 | 0 words | audio | https://learningenglish.voanews.com/a/1977695.html |
| 16 | 0 words | audio | https://learningenglish.voanews.com/a/6996501.html |
| 17 | 0 words | audio | https://learningenglish.voanews.com/a/4616316.html |
| 18 | 0 words | audio | https://learningenglish.voanews.com/a/3683470.html |
| 19 | 0 words | gallery | https://learningenglish.voanews.com/a/october-4-2021-day-in-photos/6256997.html |
| 20 | 0 words | audio | https://learningenglish.voanews.com/a/2238720.html |
| 21 | 0 words | audio | https://learningenglish.voanews.com/a/6526744.html |
| 22 | 0 words | audio | https://learningenglish.voanews.com/a/elon-musk-asks-twitter-about-selling-tesla-stock/6304945.html |
| 23 | 0 words | audio | https://learningenglish.voanews.com/a/2242779.html |
| 24 | 0 words | audio | https://learningenglish.voanews.com/a/6315561.html |
| 25 | 0 words | audio | https://learningenglish.voanews.com/a/4968931.html |
| 26 | 0 words | audio | https://learningenglish.voanews.com/a/2076984.html |
| 27 | 0 words | audio | https://learningenglish.voanews.com/a/7186376.html |
| 28 | 0 words | audio | https://learningenglish.voanews.com/a/2470810.html |
| 29 | 0 words | audio | https://learningenglish.voanews.com/a/5493526.html |
| 30 | 0 words | audio | https://learningenglish.voanews.com/a/4769009.html |
| 31 | 0 words | audio | https://learningenglish.voanews.com/a/2268087.html |
| 32 | 0 words | audio | https://learningenglish.voanews.com/a/2501409.html |
| 33 | 0 words | audio | https://learningenglish.voanews.com/a/3062388.html |
| 34 | 0 words | audio | https://learningenglish.voanews.com/a/3359404.html |
| 35 | 0 words | audio | https://learningenglish.voanews.com/a/6683538.html |
| 36 | 0 words | audio | https://learningenglish.voanews.com/a/3298564.html |
| 37 | 0 words | audio | https://learningenglish.voanews.com/a/1978970.html |
| 38 | 0 words | audio | https://learningenglish.voanews.com/a/2625122.html |
| 39 | 0 words | audio | https://learningenglish.voanews.com/a/2335465.html |
| 40 | 0 words | widget | https://learningenglish.voanews.com/a/4947127.html |
| 41 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/polio-somalia-salmon-alaska-sockeye-video-lucy-desi/1723062.html |
| 42 | 1-99 words | gallery | https://learningenglish.voanews.com/a/september-27-2023-day-in-photos/7287609.html |
| 43 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/1920194.html |
| 44 | 1-99 words | gallery | https://learningenglish.voanews.com/a/december-27-2024-day-in-photos/7916442.html |
| 45 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/johnny-appleseed-american-frontier/1248938.html |
| 46 | 1-99 words | gallery | https://learningenglish.voanews.com/a/february-14-2023-day-in-photos/6963069.html |
| 47 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/1801065.html |
| 48 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/andrew-jackson-rachel-1828-election-john-quincy-adams/1742793.html |
| 49 | 1-99 words | video | https://learningenglish.voanews.com/a/7037928.html |
| 50 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/pakistani-forces-stop-another-attack-in-karachi/1933581.html |
| 51 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/vinyl-usher-rush-josh-turner-confessions/1216840.html |
| 52 | 1-99 words | gallery | https://learningenglish.voanews.com/a/december-6-2024-day-in-photos/7890356.html |
| 53 | 1-99 words | gallery | https://learningenglish.voanews.com/a/may-7-2024-day-in-photos/7601857.html |
| 54 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/preventing-newborn-deaths-pregnant-women-need-iodine/1934019.html |
| 55 | 1-99 words | MISSED | https://learningenglish.voanews.com/a/small-business-survival-family-owned-businesses/1248743.html |

## Breakdown

Shares with Wilson 95% intervals, and the pages that share implies across the whole group.

zero (27,118 pages, sample 40):

| label | sample | share | 95% interval | pages (point) | low | high |
|---|---|---|---|---|---|---|
| audio-only | 36/40 | 90% | 76.9%-96.0% | 24,406 | 20,867 | 26,045 |
| other-widget | 3/40 | 8% | 2.6%-19.9% | 2,034 | 701 | 5,387 |
| other-gallery | 1/40 | 2% | 0.4%-12.9% | 678 | 120 | 3,493 |

short (1,768 pages, sample 15):

| label | sample | share | 95% interval | pages (point) | low | high |
|---|---|---|---|---|---|---|
| missed-article | 9/15 | 60% | 35.7%-80.2% | 1,061 | 632 | 1,418 |
| other-gallery | 5/15 | 33% | 15.2%-58.3% | 589 | 268 | 1,031 |
| video-only | 1/15 | 7% | 1.2%-29.8% | 118 | 21 | 527 |

Not in the sample, so not estimated beyond the interval: section-index, paywall, error, redirect
(0 of 55 each).

## The census

Words inside `#article-content` that the parser never read, per group:

| pages | count | any unread text | unread >= 100 words | unread >= 250 words | same title as a passage |
|---|---|---|---|---|---|
| no article text (0 words) | 27,118 | 1131 | 1 | 0 | 7,700 |
| 1-99 words | 1,768 | 1082 | 942 | 920 | - |
| passages (100+ words) | 18,968 | 575 | 40 | 26 | - |

- 0-word pages: 1,131 have some unread text and all but one have under 100 words. 25,809 of the 27,118
  have no `#article-content` at all.
- 1-99-word pages: 920 of the 942 have 250 or more unread words. Of the 826 others, 512 are The Day in
  Photos pages; the rest include Let's Learn English video lesson pages.
- Passages: 40 of the 18,968 have 100 or more unread words (26 have 250 or more), so a part of the
  body was read and a part was not. These pages are already counted with the wrong length and grade.

Check against the sample: all 55 labels agree with the census rule (the 9 missed articles have 306 to
1,609 unread words, the other 46 have 0, except one gallery with 11). The rule was written after the
sample was read, so this checks the rule, it does not test it independently. The independent evidence
is the rule applied to all 47,854 pages.

## What defeated the parser

A page from 2012-2014 (`/a/johnny-appleseed-american-frontier/1248938.html`):

```html
<div id="article-content" class="content-floated-wrap fb-quotable">
  <div class="wsw"><div class="wordclick">
    FAITH LAPIDUS: I’m Faith Lapidus.<br /> <br />
    STEVE EMBER: And I’m Steve Ember with the VOA Special English program PEOPLE IN AMERICA. ...<br /> <br />
```

`_ArticleParser` (`tools/voa_inventory/parse.py`) opens a buffer only on `<p>`, `<h2>`, `<h3>` and
`<figcaption>` (line 61) and `handle_data` drops text when no buffer is open (line 80). Bare text in a
`div` never reaches `Article.paragraphs`, so the page reads as the few `<p>` that wrap the player.
`div.wsw` is the VOA editor's body container; `div.wordclick` is the clickable-word wrapper of the
Special English scripts. Of the 9 sampled misses, 7 have the text straight in `div.wsw` and 2 inside
`div.wordclick`.

## The fix

The plan was to read text outside `p`, `h2`, `h3`, `figcaption` inside `#article-content`, split on
`<br />`, keep document order and skip the boxes the census skips. It is in `voa_inventory/parse.py`
(about 45 lines with comments). Where it differs from the plan, because of what the pages contain:

- The text is read only inside `div.wsw`, the body container. The census rule (anything in
  `#article-content` outside the skipped boxes) would have read the page title, the related-item blocks, the
  share widgets and the gallery lightbox text, which sit in the same container but outside `div.wsw`.
- Skipped inside the body: `wsw__embed` and `c-mmp` (the player), `quiz`, `content-redirect` ("We are sorry, but
  this feature is currently not available", 191 pages), lists, tables, `<h1>` and `<h4>`-`<h6>`, scripts. A
  line that is only link text ("Download PDF of this story") or that holds an MP3 link ("Or download MP3
  (Right-click ...)", 244 pages, link written `.Mp3`) is dropped; a link inside a sentence stays.
- Every `<br />` ends a paragraph, not only a pair: 4.5% of the line breaks are single.
- A bare `____` line now starts the glossary, so on 14 pages the "Words in This Story" entries leave the body.

Checked against the cache: the parser's output changes on 2,436 pages; every page the census listed with 100
or more unread words now reads 100 or more words, and 7 more do (short lines the census ignored).

## Effect on the level 4 count

Prototype, outside the repository: the unread text nodes added as paragraphs, then `voa_corpus`
measure and `blockers` unchanged. The 942 pages become passages (925 pass the licence check).

| blocked by | pages |
|---|---|
| nothing: usable as is | 34 |
| boilerplate only | 97 |
| length only | 22 |
| readability only | 93 |
| two or more of the above | 696 |

So "as is" goes from 76 to about 110. It is approximate: nodes under 40 characters are left out and
copies are not removed. The 26 partly read passages are not in it. **Measured after the fix: 98**, not 110,
because the lines under 40 characters carry most of the script boilerplate (`voa-corpus.md`).

## What the sample can and cannot support

- It supports the labels of the 0-word pages (90% audio) and says the 1-99 group is mostly missed
  articles. It cannot give the 0-word miss rate more tightly than 0-8.8%; 40 pages is too few.
- Subtypes are too small to rank: widgets 3 of 40, galleries 1 of 40, video 1 of 15.
- One reader labelled the pages. The census is the second opinion and agrees on all 55.
- The census sees one mechanism: text inside `#article-content` outside the read tags. For the 25,809
  zero-word pages with no container, a one-off scan (any text node of 200+ characters with 3+
  sentences, script text excluded; the script was not kept) found 4 pages, all programme or quiz
  blurbs of 41-47 words. A page that keeps its text somewhere else, in a form that scan misses, would
  not show up.
- The cache holds 47,854 of the 67,337 pages of the site (71%). The rest were never fetched.

## Other findings

- **Audio twins.** 7,700 of the 27,118 text-less pages (28%) have exactly the title of a passage; 12
  of 40 in the sample (30%, 18-45%). They look like the audio version of text already counted, and
  the true share is higher (titles differ slightly between the pair, for example sample 12). Pairing
  them would give listening audio for existing passages: in `docs/backlog.md`, not built.
- **Widgets.** Quiz and Word of the Day pages hold their content in script, so the cache has no text
  for them.

## Reproduce

```bash
make voa-missing                   # about 4 minutes; two runs are byte-identical
make voa-missing ARGS=--skeleton   # the drawn sample as an empty labels file
```

Both work only on the parser of `62b6669`: after the fix the draw differs from the labels file.
