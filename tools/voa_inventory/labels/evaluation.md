### How the tagger was chosen

Four taggers are scored on the same labelled pages. `keyword-v1 on pre-fix text` is the first tagger (bare
keywords, `topics_v1.yaml`) fed the first paragraph as extracted before the audio-player fix,
which for most pages was the placeholder "No media source currently available"; it is how
every count before the fix was made. `keyword-v1` is the same tagger on the corrected text.
`phrase` (phrases plus stop patterns) and `embedding` (bge-m3 similarity to a description per
topic) were built and fixed in `topics.yaml` before any label existed.

**Labelled set: 100 usable level 4 pages, drawn at random (seed 20260930), each given
one label by one person (the owner).** There is no second labeller, so label noise is
unmeasured. Units 1 and 5 follow the PLAN-v7 4.1 swap (`technology_devices`,
`nature_environment`); the phrase lists and the similarity floor were not changed.

A rate is shown only for a label with at least 10 labelled pages
(**`hobbies_leisure` 22, `language_learning` 34**). Every other row shows raw
counts (tp correct tags, fp wrong tags, fn missed pages): the sample is too small to measure
it. Among the plan topics that is `technology_devices` 3, `study_work` 5, `family_friends` 3, `food_restaurant` 5, `nature_environment` 5, `travel_transport` 1, `shopping` 0.

Plan topics (unit order):

| Topic | Labelled | keyword-v1 on pre-fix text | keyword-v1 | phrase | embedding |
|---|---|---|---|---|---|
| `technology_devices` | 3 | tp 0 · fp 1 · fn 3 | tp 0 · fp 1 · fn 3 | tp 0 · fp 1 · fn 3 | tp 0 · fp 1 · fn 3 |
| `study_work` | 5 | tp 0 · fp 3 · fn 5 | tp 1 · fp 7 · fn 4 | tp 2 · fp 6 · fn 3 | tp 0 · fp 7 · fn 5 |
| `family_friends` | 3 | tp 2 · fp 4 · fn 1 | tp 2 · fp 5 · fn 1 | tp 2 · fp 5 · fn 1 | tp 1 · fp 3 · fn 2 |
| `food_restaurant` | 5 | tp 4 · fp 2 · fn 1 | tp 4 · fp 2 · fn 1 | tp 2 · fp 1 · fn 3 | tp 4 · fp 2 · fn 1 |
| `nature_environment` | 5 | tp 1 · fp 1 · fn 4 | tp 2 · fp 1 · fn 3 | tp 3 · fp 0 · fn 2 | tp 3 · fp 2 · fn 2 |
| `hobbies_leisure` | 22 | P 0.71 (5/7)<br>R 0.23 (5/22) | P 0.67 (6/9)<br>R 0.27 (6/22) | P 0.71 (5/7)<br>R 0.23 (5/22) | P 1.00 (2/2)<br>R 0.09 (2/22) |
| `travel_transport` | 1 | tp 0 · fp 7 · fn 1 | tp 0 · fp 9 · fn 1 | tp 0 · fp 6 · fn 1 | tp 0 · fp 0 · fn 1 |
| `shopping` | 0 | tp 0 · fp 3 · fn 0 | tp 0 · fp 3 · fn 0 | tp 0 · fp 3 · fn 0 | tp 0 · fp 0 · fn 0 |

Replacement candidates:

| Topic | Labelled | keyword-v1 on pre-fix text | keyword-v1 | phrase | embedding |
|---|---|---|---|---|---|
| `health_body` | 4 | tp 1 · fp 1 · fn 3 | tp 2 · fp 1 · fn 2 | tp 2 · fp 1 · fn 2 | tp 1 · fp 0 · fn 3 |
| `weather_seasons` | 1 | tp 0 · fp 2 · fn 1 | tp 0 · fp 4 · fn 1 | tp 0 · fp 3 · fn 1 | tp 0 · fp 4 · fn 1 |
| `animals_pets` | 4 | tp 2 · fp 0 · fn 2 | tp 2 · fp 0 · fn 2 | tp 2 · fp 0 · fn 2 | tp 3 · fp 1 · fn 1 |
| `festivals_holidays` | 4 | tp 0 · fp 0 · fn 4 | tp 0 · fp 0 · fn 4 | tp 0 · fp 0 · fn 4 | tp 1 · fp 5 · fn 3 |
| `self_hometown` | 0 | tp 0 · fp 0 · fn 0 | tp 0 · fp 1 · fn 0 | tp 0 · fp 0 · fn 0 | tp 0 · fp 7 · fn 0 |
| `daily_routine` | 0 | tp 0 · fp 1 · fn 0 | tp 0 · fp 2 · fn 0 | tp 0 · fp 1 · fn 0 | tp 0 · fp 4 · fn 0 |
| `housing_home` | 1 | tp 0 · fp 0 · fn 1 | tp 0 · fp 1 · fn 1 | tp 0 · fp 0 · fn 1 | tp 1 · fp 0 · fn 0 |
| `language_learning` | 34 | P 0.89 (8/9)<br>R 0.24 (8/34) | P 0.93 (14/15)<br>R 0.41 (14/34) | P 1.00 (11/11)<br>R 0.32 (11/34) | P 0.88 (14/16)<br>R 0.41 (14/34) |
| `money_banking` | 2 | tp 0 · fp 0 · fn 2 | tp 1 · fp 1 · fn 1 | tp 2 · fp 1 · fn 0 | tp 2 · fp 0 · fn 0 |

Macro P and R average only the 2 measurable labels above, unweighted. Pooled P and R
add up the counts over the eight plan topics (44 labelled pages, 22 of
them `hobbies_leisure`, so the pool mostly measures that one topic):

| Tagger | Macro P | Macro R | Pooled P (8 plan) | Pooled R (8 plan) | F0.5 |
|---|---|---|---|---|---|
| keyword-v1 on pre-fix text | 0.80 | 0.23 | 0.34 (12/35) | 0.27 (12/44) | 0.33 |
| keyword-v1 | 0.80 | 0.34 | 0.33 (15/46) | 0.34 (15/44) | 0.33 |
| phrase | 0.86 | 0.28 | 0.37 (14/38) | 0.32 (14/44) | 0.36 |
| embedding | 0.94 | 0.25 | 0.40 (10/25) | 0.23 (10/44) | 0.35 |

Rule (fixed before labelling): the higher pooled F0.5 of `phrase` and `embedding` on the
eight plan topics, `phrase` if within 0.02. **Chosen: `phrase`.**

**Every count published before the fix was measured on placeholder text and is
void.** For 100 of the 100 labelled pages the pre-fix first paragraph was player
or download boilerplate, so the old tagger in effect read the title only. On these pages,
over the eight plan topics: they were not upper bounds. Too high: `family_friends` 6 tagged vs 3 labelled, `food_restaurant` 6 tagged vs 5 labelled, `travel_transport` 7 tagged vs 1 labelled, `shopping` 3 tagged vs 0 labelled. Too low: `technology_devices` 1 tagged vs 3 labelled, `study_work` 3 tagged vs 5 labelled, `nature_environment` 2 tagged vs 5 labelled, `hobbies_leisure` 7 tagged vs 22 labelled.

What the bug cost, pooled over the plan topics: `keyword-v1 on pre-fix text` 12 of 35 tags correct (95% interval 0.21-0.51), recall
0.27; the same tagger on corrected text 15 of 46 tags correct (95% interval 0.21-0.47), recall
0.34; `phrase` 14 of 38 tags correct (95% interval 0.23-0.53), recall 0.32. The bug cost
recall, not precision; the wrong tags come from the taggers themselves. With
0.37 of `phrase` tags correct and 0.32 of labelled pages found,
a per-topic tagger count below is a list of pages to read, not a supply figure.

### Finding: 34 of 100 usable level 4 pages teach English, not a life topic

Of the 100 labelled usable level 4 pages, `language_learning` (pages about English itself: grammar,
idioms, *Let's Learn English* lessons) is 34/100 = 34% (95% interval 25%-44%). Those pages cannot be a unit's
life-topic passage. One of the eight plan topics is 44/100 = 44% (95% interval 35%-54%); a replacement
candidate other than `language_learning` is 16/100 = 16% (95% interval 10%-24%); `none` is
6.

The crawl holds 291 usable level 4 pages at 12.1% coverage,
roughly 2405 on the whole site. Each plan topic's labelled share, as a 95% interval,
scaled to those pools (owner labels, not tagger output):

| Unit | Topic | Labelled | Crawl, usable lv 4 | Whole site, usable lv 4 |
|---|---|---|---|---|
| 1 | `technology_devices` | 3 | 3-25 | 25-203 |
| 2 | `study_work` | 5 | 6-33 | 52-269 |
| 3 | `family_friends` | 3 | 3-25 | 25-203 |
| 4 | `food_restaurant` | 5 | 6-33 | 52-269 |
| 5 | `nature_environment` | 5 | 6-33 | 52-269 |
| 6 | `hobbies_leisure` | 22 | 44-90 | 361-747 |
| 7 | `travel_transport` | 1 | 1-16 | 4-131 |
| 8 | `shopping` | 0 | 0-11 | 0-89 |

A unit needs one source passage and the report asks for 2 per topic. The lower end of
the whole-site interval reaches 2 for **7 of 8** plan topics. Not
confirmed: `shopping` (0 labelled, at most 89 whole site). Outside `hobbies_leisure`, no plan topic has more
than 5 of 100 labelled pages, so finding a unit's passage means reading pages: the
taggers above miss most of them.
