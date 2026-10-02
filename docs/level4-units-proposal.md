# Level 4 units: proposal from the corpus

Status: **proposal for the owner to read; PLAN-v7 4.1 is unchanged.** Written 2026-10-02.

The current unit list was written before the corpus was inventoried. Three of its topics have
failed on inspection: `self_hometown` has no item, `daily_routine` has one tagged item, and the
five pages tagged `shopping` are about healthy food, a vinyl music store, a rap and fashion
scene, a news round-up and farmers markets. Only the last is arguably near shopping, and no page
was labelled `shopping` by the owner. Three more (`technology_devices`, `family_friends`,
`travel_transport`) have three or fewer owner-labelled pages. ADR-0006 says the curriculum follows
the corpus. This document applies that to the whole list at once, not one topic at a time.

## 1. What the corpus contains

### Ground truth: the owner's 100 labels

`tools/voa_inventory/labels/topic_labels.csv` is a uniform random sample of usable level 4
pages. It has one label per page, and one person (the owner) labelled every page. Every
page in it is usable at level 4, so each count below is also that label's count of usable
level 4 pages in the sample.

| Label | Pages | | Label | Pages |
|---|---|---|---|---|
| `language_learning` | 34 | | `animals_pets` | 4 |
| `hobbies_leisure` | 22 | | `festivals_holidays` | 4 |
| `none` | 6 | | `health_body` | 4 |
| `study_work` | 5 | | `family_friends` | 3 |
| `food_restaurant` | 5 | | `technology_devices` | 3 |
| `nature_environment` | 5 | | `money_banking` | 2 |
| | | | `housing_home`, `weather_seasons`, `travel_transport` | 1 each |
| | | | `self_hometown`, `daily_routine`, `shopping` | 0 each |

`hobbies_leisure` is not one topic. By title, its 22 pages are **8 short-story excerpts**
(*American Stories*: Jack London, Stephen Crane, O. Henry, Washington Irving, Burroughs),
**7 music**, **3 sport**, 2 dance or art, and 2 poetry or writers. The fiction excerpts are
narratives on many subjects. None of them is about a hobby, so they cannot be a topic
unit's source.

The labels count pages. A label with 5 or fewer pages is a share estimate of 0-12%. It does
not say whether three good passages exist, so section 2 reads the whole crawl.

### The whole crawl, read by title

When this was written the crawl held **394 usable level 4 pages at about 17% coverage**.
The programme names alone split them:

| Group | Pages | Share | Usable as a topic unit's source |
|---|---|---|---|
| English lessons (*Words and Their Stories*, *Everyday Grammar*, *Ask a Teacher*) | 167 | 42% | No: about English itself |
| Fiction (*American Stories*) | 39 | 10% | No: narrative, not topical |
| Everything else (*As It Is*, *Trending Today*, *Health & Lifestyle*, *Arts & Culture*, *Education*, *National Parks*, ...) | 188 | 48% | Yes, after reading |

That 42% agrees with the labelled 34% (95% interval 25-44%). Every one of the 188 titles in
the last row was read. Where a title was ambiguous, its first paragraph was read too. Each
page went to at most one group. Where the owner had labelled a page, the owner's label won
(four pages moved this way: the fathers-at-school, harmonica, Father's Day and napping-day
pages). Lists, counts and owner labels are in the appendix.

**Who confirmed what.** The 100 owner labels are the ground truth for the distribution. The
title reads of the other pages were done by Claude for this proposal: one more reader, not a
second labeller. A title read confirms the subject, not that the passage suits a lesson.
P50 still reads the chosen passage in full. Three kinds of page were left out of every
list: wine, beer, guns and violent or political news, as unsuitable for the audience;
round-ups that cover several unrelated stories (*American Mosaic*, "COP21, Kobe Bryant,
Cyber Monday"); and the *What It Takes* interviews (3,900-6,900
words each).

## 2. Proposed units

Rules: at least 3 confirmed level 4 items per unit; a real IELTS speaking topic; no
`language_learning`. "Comfortable" here means **at least 6 confirmed items 250-1,200 words
long**. A unit uses one passage, P50 can reject several on reading (difficulty, length,
grammar fit), and the crawl is at 17%. This threshold was set before the lists were
counted.

| # | Unit | Confirmed (in length) | Owner-labelled among them | IELTS fit |
|---|---|---|---|---|
| 1 | Healthy habits (sleep, stress, breathing, goals) | 11 (11) | 4 | Part 1: sleep, daily routine, keeping healthy |
| 2 | Study and work | 12 (12) | 3 | Part 1: "Do you work or study?" (an opening topic) |
| 3 | Food and eating | 10 (10) | 4 | Part 1: food, cooking, eating out |
| 4 | Technology in daily life | 12 (12) | 1 | Part 1: phones, the internet, apps; Part 3 technology |
| 5 | Animals | 13 (13) | 4 | Part 1: animals, pets; Part 2: an animal |
| 6 | Music | 13 (13) | 5 | Part 1: music; Part 2: a song, a musician |
| 7 | Nature and places to visit | 19 (18) | 6 | Part 1: parks, nature, travel; Part 2: a place you visited |
| 8 | Sport | 14 (14) | 3 | Part 1: sport, exercise; Part 2: a sport, an athlete |

**All eight clear the comfortable margin.** None sits near the floor of 3. The thinnest
in owner evidence is Technology: 12 by title but only 1 owner-labelled page, and much of
it dates from 2010-2017 (Twitter limits, Apple TV, Facebook inbox). The owner should read
those titles first. Health has two marginal medical items ("Electric Shocks ... Brain
Disease", "Why Doctors May Not Always Try to Save a Fingertip"). Without them it still
has 9.

So the sample does support 8 units, but not the original 8. It also supports no more than
these with margin. The reserves fall short:

| Reserve | Confirmed | Verdict |
|---|---|---|
| Films and TV | 8 (6 in length), 0 owner-labelled | A clean 9th or a swap for Technology; Part 1: films, TV |
| Family and friends | 6 (5), 3 owner-labelled | Below margin; Part 1: family, friends |
| Festivals | 4 (3), 3 owner-labelled | Below margin; Part 1: festivals, holidays |
| Self and hometown, daily routine, shopping, home, weather, transport | 0-3 each | Not supportable |

## 3. Grammar and pronunciation, from the candidate passages

Each candidate passage's full body text was run through spaCy `en_core_web_sm` with simple
token, tag and dependency patterns: 21 grammar patterns. CMUdict was used on its content
words (stop words and names removed) for the 8 pronunciation features of the current
table. Each unit's rate was compared with the rate over all 122 candidate passages. "Ratio"
below is unit rate ÷ pool rate. "In" is how many of the unit's passages contain the pattern
at least twice, which is what matters when one passage is chosen. The patterns are rough
(no hand check of matches), and these are ad-hoc counters, not the P-task pattern library.

**Grammar differs a lot by topic**, because genre follows topic. Musician and animal stories
are past-tense narratives, technology pieces explain what devices can do, and sport reports
achievements. **Pronunciation hardly differs.** Four of the eight features (final /s z/, /ɪ iː/, final
clusters, two-syllable stress) stay within about 0.85-1.15 of the pool in every unit. Only
`-ed` endings, /θ ð/ and /æ e/ vary much.
So the pronunciation column is a fair assignment of the existing eight foci to units
(densest unit first, paired with the grammar where that helps), not a strong signal.

| # | Unit | Grammar point (ratio, in) | Runner-up | Pronunciation (ratio, in) |
|---|---|---|---|---|
| 1 | Healthy habits | Present simple + frequency adverbs (2.19, 6/11; present simple 1.28, 11/11) | if-clauses (1.94, 5/11) | /θ ð/ (1.49, 11/11) |
| 2 | Study and work | want / need / plan / hope + to-infinitive (1.45, 10/12) | should / must / have to (1.94, 4/12) | Two-syllable word stress (1.12, flat) |
| 3 | Food and eating | Countable/uncountable: much, many, a lot of, few, little (1.30, 6/10) | Present continuous for trends (1.64, 5/10) | Final /s z/ in plurals (1.04, flat) |
| 4 | Technology | can / could for ability and possibility (2.26, 11/12) | First conditional, if + will (if 2.41, 7/12; will 2.08, 6/12) | /ʃ/ vs /s/ (1.18, 12/12) |
| 5 | Animals | Past simple, regular and irregular (1.57, 13/13) | Passive (1.16, 8/13) | `-ed` endings /t d ɪd/ (1.32, 13/13) |
| 6 | Music | Past simple with when-clauses (when 1.52, 6/13; past 1.41, 13/13) | Past continuous (1.94, but 2/13) | /æ/ vs /e/ (1.16, 13/13) |
| 7 | Nature and places | Comparatives and superlatives (superlative 1.65, 12/19; comparative in 16/19) | Passive (1.32, 17/19) | /ɪ/ vs /iː/ (0.98, flat) |
| 8 | Sport | Present perfect (1.66, 9/14) | Superlatives (1.28, 9/14) | Final clusters /st ks nts/ (1.12, 14/14) |

What changed against the current grammar column:

- **Present continuous is gone.** Its densest units (Food 1.64, Technology 1.52) both have a
  stronger point. It remains the runner-up for Food.
- **"have got" and possessives are gone with Family.** "would you like" / "would like" occurs 0 times in
  the 10 food passages: they are news articles, not restaurant dialogues. The
  point is countable/uncountable alone.
- **Present simple with frequency adverbs** now sits in Healthy habits. Those passages are
  the densest for both, and the unit takes over what `daily_routine` was meant to teach.
- **want/plan + to-infinitive** and **can/could** are new. Each is the strongest signal in
  its unit.
- The order runs from present simple through past simple to present perfect, so the
  sequence is also a plausible grammar progression for A2-B1.

As PLAN §5.4 says, these remain candidates. The final point is whichever one the chosen
passage contains.

## 4. What this costs

The official IELTS description says Part 1 is about "familiar topics such as home, family,
work, studies and interests". Against that list:

| Part 1 topic | Covered? |
|---|---|
| Work or studies | Yes (unit 2) |
| Interests: music, sport, food, technology, animals, nature, travel | Yes (units 3-8) |
| Daily routine, sleep | Partly (unit 1, through health habits) |
| **Hometown / the area you live in** | **No** |
| **Home / accommodation** | **No** |
| **Family, friends** | **No** (reserve, below margin) |
| Shopping, clothes, weather, transport, festivals, weekends, neighbours | No |

**Does it matter at band 4.5-5.0?** Partly. The rotating Part 1 topics (shopping, weather,
transport, festivals) are one of many possible sets in a given test. Missing them costs
little, and the grammar and pronunciation transfer. **Hometown and home are different**:
one of them, or work/study, opens nearly every Part 1. At this band, a candidate who has
never answered "Tell me about your hometown" loses fluency exactly where the examiner
forms a first impression. Family is close behind. This is a real gap.

ADR-0006 does not forbid closing it without source text. The rule bans generated
*English source text*; questions are scaffolding. A short speaking-only "Part 1 starter"
with examiner-style questions on hometown, home and family would need no VOA passage.
It is in `docs/backlog.md` and is not part of this proposal.

## 5. Decisions for the owner

1. Accept the eight units, or swap Technology for Films and TV after reading both lists.
2. Spot-check the title reads (the appendix marks every owner-labelled item).
3. Decide whether the Part 1 starter goes into the MVP scope (backlog).
4. Then PLAN-v7 4.1 is rewritten from this document, in one change.

Reproduce: the lists come from the crawl cache and are not regenerated by any make target.
The spaCy and CMUdict counts came from a one-off script and are not in the repo. When P51
builds the grammar pattern library, re-run it against these passages.

## Appendix: candidate items per unit

Body word counts come from the cleaned article body (alphabetic tokens). "owner:" gives the
owner's label where the page is in the labelled sample.

### Unit 1 · Healthy habits: 11 confirmed by title, 11 of 250-1,200 words, 4 also owner-labelled

- [A Look Back on Health, Lifestyle in 2015](https://learningenglish.voanews.com/a/top-health-lifestyle-stories-2015/3121130.html) · 845 words · owner: `health_body`
- [Deep Breathing Helps the Lungs](https://learningenglish.voanews.com/a/deep-breathing-helps-the-lungs/5562324.html) · 493 words
- [Electric Shocks, Not Drugs, Help A Brain Disease.](https://learningenglish.voanews.com/a/electric-shocks-not-drugs-help-a-brain-disease-/1938856.html) · 472 words
- [Harmonica Playing Good for Body and Soul](https://learningenglish.voanews.com/a/harmonica-playing-good-for-body-and-soul/3837841.html) · 717 words · owner: `health_body`
- [How to Be Productive During Difficult Times](https://learningenglish.voanews.com/a/how-to-be-productive-during-difficult-times/5693184.html) · 828 words
- [Rich People Even Have Better Stress Than Poor](https://learningenglish.voanews.com/a/rich-people-haver-better-stress-than-poor/3329623.html) · 714 words
- [Study Links Bedtime Rules to Better Skills in Preschool Children](https://learningenglish.voanews.com/a/study-links-bedtime-rules-to-better-skills--95922384/114919.html) · 451 words · owner: `health_body`
- [Understanding Your Brain and Clutter](https://learningenglish.voanews.com/a/understanding-your-brain-and-clutter-/5421968.html) · 867 words · owner: `health_body`
- [Ways to Achieve Your Goals](https://learningenglish.voanews.com/a/ways-to-achieve-your-goals/4758976.html) · 770 words
- [Why Doctors May Not Always Try to Save a Fingertip](https://learningenglish.voanews.com/a/why-doctors-may-not-always-try-to-save-a-fingertip-115074799/115141.html) · 504 words
- [Your Bones Are Alive! Learn How to Keep Them Strong](https://learningenglish.voanews.com/a/health-and-lifestyle-bones-are-alive/3832858.html) · 990 words


### Unit 2 · Study and work: 12 confirmed by title, 12 of 250-1,200 words, 3 also owner-labelled

- [Afghan, Vietnamese Students Thrive in US Schools](https://learningenglish.voanews.com/a/children-of-afghan-and-vietnamese-immigrants-to-us-succeed-in-school/3375034.html) · 668 words
- [Almost a Dream: Going to College from Home](https://learningenglish.voanews.com/a/almost-a-dream-going-to-college-from-home/5596636.html) · 925 words
- [Children of Indian Immigrants Win Spelling Bee](https://learningenglish.voanews.com/a/spelling-bee-winners/3349098.html) · 399 words
- [College Admissions: Teaching Parents How to Help](https://learningenglish.voanews.com/a/college-admissions-advice-for-parents/4126961.html) · 893 words
- [Education Activist Praises Gains for Girls in Uganda](https://learningenglish.voanews.com/a/uganda-girls-school-lords-resistance-ted-talk/2579624.html) · 497 words
- [Experimental School in California Has No Homework](https://learningenglish.voanews.com/a/experimental-school-california-no-homework/3681464.html) · 691 words
- [Experts Share Tips for Writing School Papers](https://learningenglish.voanews.com/a/writing-school-papers/2423454.html) · 629 words
- [Media Program Helps Young People in Washington, DC](https://learningenglish.voanews.com/a/media-program-helps-young-people-in-washington-dc/7366844.html) · 909 words · owner: `study_work`
- [Secrets of a Saddle-Maker](https://learningenglish.voanews.com/a/secrets-of-a-saddle-maker/2687090.html) · 457 words · owner: `study_work`
- [Student Walks 32 Kilometers to New Job](https://learningenglish.voanews.com/a/student-walks-32-kilometers-to-new-job/4489870.html) · 390 words
- [Want a Response to Your Email? Follow These Tips](https://learningenglish.voanews.com/a/tips-for-email/3842882.html) · 1104 words · owner: `study_work`
- [Writing Groups Can Help Students with Papers](https://learningenglish.voanews.com/a/writing-groups-can-help-students-with-papers/2500440.html) · 476 words


### Unit 3 · Food and eating: 10 confirmed by title, 10 of 250-1,200 words, 4 also owner-labelled

- [Americans Eating More 'Fast Casual,' Less Fast Food](https://learningenglish.voanews.com/a/americans-eating-more-fast-casual-less-fast-food/2643490.html) · 589 words · owner: `food_restaurant`
- [Cow Head Meat Popular in South Africa](https://learningenglish.voanews.com/a/cow-head-meat-popular-in-south-africa/2500997.html) · 427 words
- [Growing Vegetables Without Soil Inside the Home](https://learningenglish.voanews.com/a/growing-vegetable-without-soil/3591318.html) · 287 words
- [Immigrants Spur US Farmers Markets Revival](https://learningenglish.voanews.com/a/immigrants-spur-us-farmers-markets-revival/4609263.html) · 602 words
- [In-Store Training on Healthy Food Choices](https://learningenglish.voanews.com/a/in-store-training-on-healthy-food-choice/2863162.html) · 736 words · owner: `food_restaurant`
- [Kale: The 'Super Food'](https://learningenglish.voanews.com/a/kale-the-super-food/2476014.html) · 569 words
- [Lebanese Women Make Peace One Meal at a Time](https://learningenglish.voanews.com/a/lebanese-women-make-peace-one-meal-at-a-time/2611322.html) · 584 words
- [Meatballs Around the World](https://learningenglish.voanews.com/a/meatballs-around-the-world/4286038.html) · 752 words
- [NASA Developing Food Bars for Mars Flights](https://learningenglish.voanews.com/a/nasa-developing-food-for-mars-flights/3625387.html) · 732 words · owner: `food_restaurant`
- [Would Americans Let Edible Insects Come to Dinner?](https://learningenglish.voanews.com/a/would-americans-let-edible-insects-come-to-dinner-/4789515.html) · 685 words · owner: `food_restaurant`


### Unit 4 · Technology in daily life: 12 confirmed by title, 12 of 250-1,200 words, 1 also owner-labelled

- [Apple TV, Fire TV or Roku?](https://learningenglish.voanews.com/a/apple-tv-fire-tv-or-roku/3082835.html) · 942 words
- [Changes to Twitter Let You Say More in a Tweet](https://learningenglish.voanews.com/a/twitter-update-2016/3364301.html) · 745 words · owner: `technology_devices`
- [E-Book Lending at Libraries](https://learningenglish.voanews.com/a/e-book-lending-at-libraries-134631558/131310.html) · 252 words
- [New Computers from Microsoft and Apple](https://learningenglish.voanews.com/a/future-of-computers/3575601.html) · 722 words
- [Prisma App Makes Art Out of Photos](https://learningenglish.voanews.com/a/prisma-app/3423097.html) · 692 words
- [Robot Helps Sick Children Feel Less Lonely](https://learningenglish.voanews.com/a/health-and-lifestyle-report-robots-help-sick-children-feel-less-lonely/3559737.html) · 461 words
- [The Life of Steve Jobs](https://learningenglish.voanews.com/a/steve-jobs-remembered-133101618/131307.html) · 257 words
- [Tracking Santa with Technology](https://learningenglish.voanews.com/a/tracking-santa-with-technology/3112564.html) · 562 words
- [What to Do When Your Technology Goes Wrong](https://learningenglish.voanews.com/a/tech-problems-fixes/3564944.html) · 1049 words
- [Where to Find Your Hidden Messages on Facebook](https://learningenglish.voanews.com/a/facebook-hidden-messages/3293621.html) · 454 words
- [Will Robots Replace Humans in Food Industry?](https://learningenglish.voanews.com/a/food-robots/3617642.html) · 528 words
- [Young Programmer’s App Helps War Veteran Father Sleep Better](https://learningenglish.voanews.com/a/programmer-helps-veteran-father-sleep/3482500.html) · 519 words


### Unit 5 · Animals: 13 confirmed by title, 13 of 250-1,200 words, 4 also owner-labelled

- ['Dog or Bread?' Question Takes Over Twitter](https://learningenglish.voanews.com/a/dog-or-bread/3232407.html) · 259 words · owner: `animals_pets`
- ['Rally Cat' Goes Viral After Baseball Game](https://learningenglish.voanews.com/a/whats-trending-rally-cat/3980604.html) · 576 words
- [Baby Eagles in Washington, DC Get Their Names](https://learningenglish.voanews.com/a/baby-eagles-names/3305323.html) · 332 words
- [Bald Eagles Hatch on Live Streaming](https://learningenglish.voanews.com/a/trending-today-march-18-2016-dc-eagle-cam/3244322.html) · 294 words
- [California Dogs Riding The Waves](https://learningenglish.voanews.com/a/california-dogs-riding-the-wave/2987759.html) · 327 words
- [California's Catalina Island Bison Bring Tourists, Concern](https://learningenglish.voanews.com/a/catalina-island-bison/3932894.html) · 519 words · owner: `animals_pets`
- [Iguana Becomes Star of Tennis Match in Miami](https://learningenglish.voanews.com/a/iguana-tennis-match/3779173.html) · 338 words
- [Mia the Beagle Acts Like a Real Dog at Westminster Dog Show](https://learningenglish.voanews.com/a/trending-today-mia-the-beagle-westminster-dog-show/3724348.html) · 314 words
- [Millions Watching Giraffe Cam](https://learningenglish.voanews.com/a/giraffe-cam/3737320.html) · 384 words
- [Think You Know How Dogs Drink Water?](https://learningenglish.voanews.com/a/how-do-dogs-drink-water/3116091.html) · 456 words
- [Trending Today: A Dramatic Owl Fly-By, a Sad Raccoon](https://learningenglish.voanews.com/a/snowy-owl-fly-by-raccoon-trick/3137369.html) · 388 words · owner: `animals_pets`
- [What Was So Cute It Stopped Traffic in San Francisco?](https://learningenglish.voanews.com/a/dog-stops-traffic-on-san-francisco-bridge/3268507.html) · 271 words
- [Zoo Animals Show Their Artistic Sides](https://learningenglish.voanews.com/a/zoo-animals-show-artistic-side/2616597.html) · 457 words · owner: `animals_pets`


### Unit 6 · Music: 13 confirmed by title, 13 of 250-1,200 words, 5 also owner-labelled

- [A Growing Rap, Fashion Scene in Northern Nigeria](https://learningenglish.voanews.com/a/a-growing-rap-and-fashion-scene-in-northern-nigeria/3767767.html) · 601 words · owner: `hobbies_leisure`
- [A Very Musical Love Story](https://learningenglish.voanews.com/a/a-very-musical-love-story/2643883.html) · 322 words
- [Blind Boy Defines His Life With Music](https://learningenglish.voanews.com/a/cole-moran-blind-music/2792610.html) · 338 words
- [Building a Truly American Instrument](https://learningenglish.voanews.com/a/building-a-truly-american-instrument/4729582.html) · 605 words
- [Goma Aims for Healing, Peace through Music](https://learningenglish.voanews.com/a/goma-aims-for-healing-peace-through-music/2652516.html) · 487 words
- [Longtime, But Unknown, Blues Musicians Release CD](https://learningenglish.voanews.com/a/blues-legends-still-carrying-flame-bb-king/2724681.html) · 400 words
- [Memories and Hopes Meet in New Year's Music](https://learningenglish.voanews.com/a/new-years-music/1813304.html) · 838 words
- [Music Artist and Singer Drake](https://learningenglish.voanews.com/a/music-artist-and-singer-drake-149067615/609700.html) · 306 words
- [Music Program at Sing Sing Prison Gives Detainees a New Start](https://learningenglish.voanews.com/a/music-program-at-sing-sing-gives-detainees-a-new-start/4312720.html) · 721 words
- [Musician Helped Define Rock n’ Roll in 1950s and 60s](https://learningenglish.voanews.com/a/musician-helped-define-rock-n-roll-in-1950s-and-60s/2825821.html) · 534 words · owner: `hobbies_leisure`
- [Musicians Aim to Keep DC's Go-go Music Going](https://learningenglish.voanews.com/a/musicians-aim-to-keep-dcs-gogo-music-going/3862013.html) · 768 words · owner: `hobbies_leisure`
- [Nairobi Music Store Sells Vinyl Records Again](https://learningenglish.voanews.com/a/nairobi-music-store-sells-vinyl-records-again/2926517.html) · 491 words · owner: `hobbies_leisure`
- [Trending Today: Sia, Jimmy Fallon and The Roots](https://learningenglish.voanews.com/a/sia-jimmy-fallon-roots/3168833.html) · 284 words · owner: `hobbies_leisure`


### Unit 7 · Nature and places to visit: 19 confirmed by title, 18 of 250-1,200 words, 6 also owner-labelled

- [Bags Help Farmers Protect Harvests From Air and Insects](https://learningenglish.voanews.com/a/farmers-helped-by-bags-that-keep-air-out-of-harvests--114944009/112166.html) · 536 words
- [Bangladesh Overcomes Flooding with 'Floating Farms'](https://learningenglish.voanews.com/a/bangladesh-floating-farms/2535772.html) · 715 words
- [Bumblebee Added to US Endangered Species List](https://learningenglish.voanews.com/a/bumblebee-endangered/3675313.html) · 319 words · owner: `nature_environment`
- [Crater Lake National Park: A Blue Jewel](https://learningenglish.voanews.com/a/americas-national-parks-crater-lake/3462291.html) · 871 words
- [Fall Colors Not Only Red and Blue](https://learningenglish.voanews.com/a/fall-colors/3581151.html) · 376 words · owner: `weather_seasons`
- [Floodwaters Threaten Famous American Home](https://learningenglish.voanews.com/a/floodweaters-threaten-famous-american-home/2857059.html) · 468 words
- [Hawaiian Canoe to Navigate Around the World](https://learningenglish.voanews.com/a/hawaiian-canoe-to-navigate-around-the-world-polynesian/1921381.html) · 525 words
- [Light Pollution. How Much Light is Too Much?](https://learningenglish.voanews.com/a/light-pollution-how-much-is-too-much/2596769.html) · 935 words
- [Mammoth Cave: Grand and Gloomy](https://learningenglish.voanews.com/a/americas-national-parks-mammoth-cave/3570577.html) · 785 words · owner: `nature_environment`
- [New Ferris Wheel Lights Up Washington, DC](https://learningenglish.voanews.com/a/ferris-wheel-washington-dc-potomac/1945868.html) · 580 words
- [Oil Company Pays for Pollution in Nigeria](https://learningenglish.voanews.com/a/oil-company-pay-for-pollution-in-nigeria/2670686.html) · 434 words · owner: `nature_environment`
- [One-Third of World’s Population Cannot See The Milky Way](https://learningenglish.voanews.com/a/one-third-of-the-world-cannot-see-the-milky-way/3391308.html) · 679 words
- [Prisoners Work to Protect the Planet](https://learningenglish.voanews.com/a/prisoners-work-to-protect-the-planet/2583701.html) · 902 words
- [Some Americans Want Fewer Grass Lawns](https://learningenglish.voanews.com/a/some-americans-want-fewer-grass-lawns/7111121.html) · 541 words
- [Switzerland Opens World's Longest Suspension Footbridge](https://learningenglish.voanews.com/a/switzerland-open-worlds-longest-suspension-bridge/3971110.html) · 193 words (short) · owner: `travel_transport`
- [The Strange and Beautiful World of Arches National Park](https://learningenglish.voanews.com/a/americas-national-parks-arches/3551240.html) · 968 words
- [Voyageurs National Park: A Land of Lakes](https://learningenglish.voanews.com/a/voyareurs-national-park-land-of-lakes/3639522.html) · 768 words
- [Where Have All the Bees Gone?](https://learningenglish.voanews.com/a/where-have-all-the-bees-gone/2722797.html) · 533 words
- [Wild Surroundings at Black Canyon of the Gunnison](https://learningenglish.voanews.com/a/americas-national-parks-black-canyon-of-the-gunnison/3541130.html) · 924 words · owner: `nature_environment`


### Unit 8 · Sport: 14 confirmed by title, 14 of 250-1,200 words, 3 also owner-labelled

- [Blind Athlete Hikes the Grand Canyon](https://learningenglish.voanews.com/a/blind-athlete-hikes-the-grand-canyon/4616164.html) · 323 words
- [Brazil Football Museum Attracts Passionate Fans](https://learningenglish.voanews.com/a/brasil-football-museum-attracts-passionate-fans/1952234.html) · 384 words · owner: `hobbies_leisure`
- [Experts Examine Links Between Brain Injuries and American Football](https://learningenglish.voanews.com/a/4028896.html) · 485 words
- [Girl Completes Backyard “Ninja Warrior” Course](https://learningenglish.voanews.com/a/girl-ninja-warrior/3541231.html) · 330 words
- [Is Lionel Messi Leaving Argentina's Soccer Team?](https://learningenglish.voanews.com/a/messi-to-leave-argentina-team/3394256.html) · 431 words
- [Mayweather Defeats Pacquiao in 'The Fight of the Century'](https://learningenglish.voanews.com/a/boxing-pac-man-money-knockout/2743641.html) · 665 words
- [Oklahoma Rodeo Celebrates Western Traditions](https://learningenglish.voanews.com/a/oklahoma-rodeo-elk-city-voa/2951376.html) · 806 words
- [Patriots, Brady and Lady Gaga Impress at Super Bowl](https://learningenglish.voanews.com/a/super-bowl-patriots-gaga/3708441.html) · 403 words
- [Refugee Football Team Aims for Greek League](https://learningenglish.voanews.com/a/refugee-football-team-aims-for-greek-league/3616523.html) · 477 words · owner: `hobbies_leisure`
- [Swimmers Trading Pools for Open Water](https://learningenglish.voanews.com/a/swimmers-trading-pools-open-water/2511950.html) · 474 words
- [Team Sports Teach Life Lessons](https://learningenglish.voanews.com/a/team-sports-teach-life-lessons/4998076.html) · 975 words
- [Trending Today: Kobe Bryant’s Final NBA Game](https://learningenglish.voanews.com/a/trending-kobe-bryant-golden-state-warriors/3285990.html) · 561 words
- [US Restaurant Serves Medieval Art of Fighting](https://learningenglish.voanews.com/a/us-restaurant-introduces-medieval-fighting/2700677.html) · 489 words
- [Young Women Train to Wrestle in Conservative Indian State](https://learningenglish.voanews.com/a/young-women-train-to-wrestle-in-conservative-indian-state/3703796.html) · 476 words · owner: `hobbies_leisure`


### Reserve · Films and TV: 8 confirmed by title, 6 of 250-1,200 words, 0 also owner-labelled

- ['Game of Thrones' Breaks Emmy Award Record](https://learningenglish.voanews.com/a/hbo-game-thrones-breaks-emmy-record/3515837.html) · 242 words (short)
- [Actress Debbie Reynolds Dies, One Day After Daughter Carrie Fisher](https://learningenglish.voanews.com/a/debbie-reynolds-dies/3655908.html) · 400 words
- [Hollywood Movies Used to Teach Science](https://learningenglish.voanews.com/a/hollywood-stuntman-helps-children-learn-science/1969942.html) · 445 words
- [Hollywood Star Pulls Driver from Burning Car](https://learningenglish.voanews.com/a/jamie-foxx-saves-driver/3154677.html) · 233 words (short)
- [Real Mermaids? Not Really, But…](https://learningenglish.voanews.com/a/real-mermaids-not-really-but/3313412.html) · 431 words
- [Trending Today: 'Fuller House' Now on Netflix](https://learningenglish.voanews.com/a/trending-today-fuller-house-netflix/3210057.html) · 323 words
- [TV Viewers Complain About Fireworks Broadcast](https://learningenglish.voanews.com/a/washington-dc-fireworks-pbs/3405239.html) · 366 words
- [“Finding Dory” Movie Audience Surprised in California](https://learningenglish.voanews.com/a/finding-dory-surprise-trailer/3400658.html) · 402 words


### Reserve · Family and friends: 6 confirmed by title, 5 of 250-1,200 words, 3 also owner-labelled

- [A Father’s Day Hashtag](https://learningenglish.voanews.com/a/dad-in-band-hashtag/3381269.html) · 376 words · owner: `family_friends`
- [Group Wants Fathers to Volunteer at US Schools](https://learningenglish.voanews.com/a/fathers-group-watch-dogs/3469429.html) · 424 words · owner: `family_friends`
- [Louisiana Boy Known as 'Drive-By Hugger' Identified](https://learningenglish.voanews.com/a/drive-by-hugger-identified/3374226.html) · 370 words · owner: `family_friends`
- [Martha Washington: First First Lady](https://learningenglish.voanews.com/a/nation-martha-washington/2905100.html) · 1232 words (long)
- [Sri Lankan-American Gives Back to Home Country](https://learningenglish.voanews.com/a/sri-lankan-american-gives-back/2666444.html) · 512 words
- [Will the US Pay Workers for Family Leave?](https://learningenglish.voanews.com/a/will-the-us-pay-workers-for-family-leave/2670749.html) · 767 words


### Reserve · Festivals: 4 confirmed by title, 3 of 250-1,200 words, 3 also owner-labelled

- [Dr. Seuss Honored on World Book Day](https://learningenglish.voanews.com/a/dr-seuss-honored-on-world-book-day/3747161.html) · 311 words · owner: `festivals_holidays`
- [Happy National Napping Day](https://learningenglish.voanews.com/a/3236302.html) · 233 words (short) · owner: `festivals_holidays`
- [New Year's Traditions Around the World](https://learningenglish.voanews.com/a/new-years-traditions-around-the-world/4183351.html) · 815 words
- [VOA Learning English Presents 'A Visit from St. Nicholas'](https://learningenglish.voanews.com/a/a-visit-from-st-nicholas/4174093.html) · 708 words · owner: `festivals_holidays`
