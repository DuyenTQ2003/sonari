# Sonari — Plan v7

Supersedes v6. Milestones are gated by completion, not by calendar weeks, because the
real constraint is session token budget.

---

## 1. What changed from v6

| Area | v6 | v7 | Cost of the change |
|---|---|---|---|
| Target exam | VSTEP first | **IELTS only**. VSTEP is dropped, not deferred | VSTEP is the graduation requirement at many VN universities, so IELTS-first narrows the "must pass" audience and widens the "wants to study abroad" one |
| Level range | CEFR B1–B2 | **7 difficulty levels** written against IELTS band 1.0–7.0 (≈ pre-A1 to C1) | Content surface grows ~3x. Mitigated by shipping one level first (§4) |
| Structure | One 22-minute lesson arc per topic | **Duolingo-style path**: Level 1–7 → Unit (topic) → 6 short lessons of ~5 min | More screens, but each lesson is small and templated |
| Skill focus | Four skills equally | **Listening + speaking first**. Reading and writing move to backlog | Scope drops. The GOP engine is used on nearly every lesson instead of once per topic |
| Gamification | Cut early | **Streak, XP and daily goal are core**. Leagues, hearts and gems stay out (§6) | About two sessions of work. Cheap relative to its retention effect |

Unchanged: ADR-0001 (architecture), ADR-0004 (LLM via API, budget < $10/month), GOP
without Whisper, the ban on scraping real exam content, the language rule, and the cut
priority (eval → observability → agent → optimization).

---

## 2. Product

**Sonari** is a topic-based English course for Vietnamese students that builds IELTS
listening and speaking. Each topic follows this path:

```
topic → vocabulary → sentences using that vocabulary → grammar → listen → speak
```

The differentiator is not pronunciation scoring, since ELSA already owns that. It is
three things together:

1. Every speaking turn is scored on three axes: pronunciation (per phoneme), fluency,
   and task completion (did you use the unit's words and grammar?).
2. Grammar is explained by contrast with Vietnamese, not by translating an English
   textbook.
3. Pronunciation drills target errors specific to Vietnamese speakers: dropped final
   consonants, clusters, /θ ð/, /ʃ/–/s/, /æ/–/e/, and word stress.

---

## 3. Level system

### 3.1 Scale: 7 difficulty levels

Levels 1–7 are the **teaching difficulty** of the curriculum. Each level raises
vocabulary range, sentence length, grammar complexity, listening speed and the length
of what the learner must say. The IELTS band next to each level is only the reference
the content is written against. It is not something the learner is told they achieved.

| Level | Content written against | CEFR (content tag) | Listening speed | Speaking demand | Topic character |
|---|---|---|---|---|---|
| 1 | band 1.0–2.0 | pre-A1 | 0.8×, single words | Say a word | Greetings, numbers, self |
| 2 | band 2.5–3.0 | A1 | 0.8×, short phrases | Say a short sentence | Family, home, daily objects |
| 3 | band 3.5–4.0 | A2 | 0.8–1.0× | Answer with one sentence | Concrete daily life |
| 4 | band 4.5–5.0 | B1 | 1.0× | 2–3 sentence answer (IELTS Part 1) | Personal experience |
| 5 | band 5.5 | B2 low | 1.0× | 30–60 s answer | Describing, narrating (Part 2) |
| 6 | band 6.0–6.5 | B2 | 1.0–1.15× | 1–2 min long turn | Opinions, reasons (Part 2–3) |
| 7 | band 7.0 | C1 entry | 1.15×, natural | Extended discussion | Abstract: comparison, speculation (Part 3) |

Difficulty is controlled by content tags that the validator checks, not by eye:
`cefrLevel`, max sentence length, word frequency band (NGSL/Oxford list), grammar
points allowed at that level, TTS speed, and minimum answer duration.

Official IELTS–CEFR alignment covers only band 4.0 and above. Mappings below band 4.0
are our own approximation, and the docs say so.

### 3.2 What the UI shows

- The level is shown as **"Cấp 4"**, optionally with the reference "(tương đương band
  4.5–5.0)". The app never says "Bạn đạt band X".
- An estimated speaking band stays behind the QWK ≥ 0.6 gate. It is a backlog feature.
- Footer: *Sonari không liên kết với IELTS, British Council, IDP hay Cambridge.*

### 3.3 Unlocking

- Units unlock in order when the previous unit is **completed**, not when it is
  **passed** at a score threshold. Gating on an unvalidated speaking score punishes
  learners for our measurement error.
- Levels unlock in order. A placement test (§7.5) can start a learner at a later level.
  It is built only once a second level exists; with one level it has nothing to place into.

---

## 4. Curriculum structure

```
Course (IELTS track)
└── Level 1..7             difficulty (§3.1)
    └── Unit                one topic, ~8 per level (level 4: 8 plus Unit 0, §4.2)
        ├── L1 Vocabulary A       6 words
        ├── L2 Vocabulary B       6 words
        ├── L3 Sentences in use   the 12 words inside real sentences
        ├── L4 Grammar            1 point, contrastive VI explanation
        ├── L5 Listening          the unit source: VOA dialogue (lv 1–3) or VOA passage (lv 4–7)
        └── L6 Speaking           roleplay (lv 1–3) or IELTS Part 1/2/3 questions (lv 4–7), 3-axis score
Review (separate mode)      FSRS queue of everything learned, daily
```

A lesson is 10–15 exercises of **mixed types** and takes about 5 minutes. Mixing types
within one lesson is the core Duolingo mechanic, not the path graphic.

### 4.1 MVP slice: Level 4, 8 units plus Unit 0

Level 4 comes first for three reasons. Most VN university targets (IELTS 4.5–5.5) sit
there. VOA Learning English content is richest at this level. And the v6 B1 work
carries over directly.

| # | Topic (VI) | Grammar point | Pronunciation focus | Confirmed items |
|---|---|---|---|---|
| 1 | Thói quen lành mạnh (Healthy habits) | Present simple with frequency adverbs | /θ/ /ð/ | 11 |
| 2 | Học tập & công việc (Study and work) | want / need / plan / hope + to-infinitive | Word stress, 2-syllable words | 12 |
| 3 | Đồ ăn (Food and eating) | Countable/uncountable: much, many, a lot of, few, little | Final /s/ /z/ in plurals | 10 |
| 4 | Công nghệ trong đời sống (Technology in daily life) | can / could for ability and possibility | /ʃ/ vs /s/ | 12 |
| 5 | Động vật (Animals) | Past simple (VI marks time with "đã", not inflection) | -ed endings /t/ /d/ /ɪd/ | 13 |
| 6 | Âm nhạc (Music) | Past simple with when-clauses | /æ/ vs /e/ | 13 |
| 7 | Thiên nhiên & địa điểm (Nature and places) | Comparatives and superlatives | /ɪ/ vs /iː/ | 19 |
| 8 | Thể thao (Sport) | Present perfect | Final clusters /st/ /ks/ /nts/ | 14 |

**How the units were chosen.** The first list was written before the corpus was
inventoried, and three of its topics then failed on inspection (hometown: no item; daily
routine: one; shopping: none about shopping). This list replaces it whole, not topic by
topic. It comes from reading, by title and where a title was ambiguous the
first paragraph, all 188 usable level-4 pages that are neither English-lesson programmes
nor fiction, at the crawl snapshot of about 17% of the site (394 usable level-4 pages in
all; 42% were English lessons, 10% fiction). The title reads were done by one reader (the
assistant), not a second labeller; the 100 owner labels (`tools/voa_inventory/labels/`)
are the only ground truth. The tagger is not evidence (P 0.37 / R 0.32). Each unit has at
least 10 candidate passages of 250–1,200 words confirmed by title. The margin rule was at
least 6, fixed before the lists were counted. Lists, counts and the reasoning are in `docs/level4-units-proposal.md`, which is the
record of how this was decided.

**Grammar column.** Each point is the strongest signal of its unit in spaCy counts over the
candidate passages (density against the pool of all 122, and how many passages contain the
pattern at least twice). It is not taken from the old table, which was written for the old
topics. Units 5 and 6 both rest on the past simple: Animals teaches the tense and Music
teaches it inside when-clauses. If the chosen passages make that redundant, §5.4 decides
the point at authoring time.

**Pronunciation column.** This is a redistribution of the eight Vietnamese-specific foci
(§2) over the units. It is not a corpus signal: four of the eight features stay within
about 0.85–1.15 of the pool in every unit, and the other four (`-ed` endings, /θ ð/, /æ e/
and /ʃ s/) vary with topic only as a side effect of genre, not as a reason to teach them.

**Reserve.** Films and TV (8 confirmed, 6 within the length range, none owner-labelled) is
the only reserve that meets the margin. Family and friends (6, of which 5 in range) and
Festivals (4, of which 3) fall below it. Topics with 0–3 items (self and hometown, daily
routine, shopping, home, weather, transport) are not supportable. Family, hometown and
home are covered by Unit 0 (§4.2) without a source passage.

The topic list and grammar column are **candidates**. Under source-first authoring
(§5.4) the final grammar point is whichever candidate the chosen VOA passage actually
contains. A unit whose passage lacks it swaps topic or grammar point, never the text.

**Volume.** 8 units: 96 words, 8 grammar points, 8 source passages and about 570
exercises (about 71 per unit). Unit 0 adds 18 words, no grammar point, no source passage
and about 70 exercises. Total: **9 units, 114 words, 8 grammar points, 8 source passages,
about 640 exercises.** **Exercises are generated from templates, not written by hand**
(§5.2).

### 4.2 Unit 0: Part 1 starter

Unit 0 opens level 4 and is speaking-only. It teaches the three topics that open almost
every IELTS Part 1 and that the corpus cannot supply: **hometown, home (accommodation) and
family.** VOA is a news site, so the closer a topic sits to everyday personal life, the
fewer items exist. A learner who has never answered "Tell me about your hometown" loses
fluency exactly where the examiner forms a first impression, and this is the largest gap
the corpus-driven list leaves (`docs/level4-units-proposal.md` §4).

- **Shape.** Three topics, each a vocabulary lesson (6 words, with example sentences) and
  a speaking lesson (Part 1 questions, scored on three axes): 6 lessons, the same count as
  every other unit. There is **no source passage, no reading and no L5 Listening lesson.**
  Pronunciation focus: none assigned.
- **Why ADR-0006 permits it.** The ADR bans generated English *source text*. Part 1
  questions are scaffolding, which the ADR lets the LLM draft, and the example sentences
  still come from Tatoeba (ADR step 5). No passage, dialogue or model answer is generated; the only
  generated English is the questions themselves. Questions are drafted fresh and never
  copied from Cambridge, British Council or IDP material.
- **What it does not do.**
  - It extracts no vocabulary from a passage, because there is none. Its 18 words come
    from the Oxford 3000 and NGSL lists for these topics, not from ADR step 2.
  - It has no grammar lesson, because §5.4 derives a grammar point from the passage
    (ADR step 3). Task completion (§7.3) therefore checks vocabulary only in this unit.
  - It has no model answers or sample responses. Those would be generated English, which
    ADR-0006 forbids.
  - It does not change the eval gates, the licensing filter or ADR-0006.

---

## 5. Content model and pipeline

### 5.1 Entities (content bounded context)

- `Learnable`: `word` | `sentence` | `grammarPoint` | `phoneme`. Carries `cefrLevel`,
  `examTags`, `topicIds`, and `origin` (`corpus` | `generated_reviewed`).
- `Unit`: topic, level, `targetVocab[]`, `targetGrammar[]`, `targetPhonemes[]`,
  `sourceId` (VOA item: URL, byline, audio).
- `Lesson`: an ordered list of exercise specs that reference learnables.
- `Exercise`: type, payload, answer key, and the audio asset key (in R2).

Learning state (FSRS cards, Elo, lesson completion) lives in the **learning** context.
Streak and XP live in **gamification**. Both consume `LessonCompleted` and
`ExerciseAnswered` events and keep local read models. There are no cross-context joins.

### 5.2 Exercise types

Each type is deterministic unless marked otherwise, so answer checking needs no LLM at
runtime.

| Type | Skill | Scoring |
|---|---|---|
| Nghe → chọn nghĩa | Listen, vocab | Exact |
| Nghe → chọn từ | Listen | Exact |
| Ghép cặp EN–VI | Vocab | Exact |
| Xếp từ thành câu (word bank) | Grammar, sentence | Accepted-order list |
| Dịch VI→EN bằng word bank | Sentence | Accepted-answer list |
| Điền chỗ trống | Grammar | Exact plus accepted variants |
| Nghe chép chính tả | Listen | Normalised token match |
| Đọc to từ / câu | Speak | **GOP** |
| Nghe và lặp lại (shadowing) | Listen, speak | **GOP** + fluency |
| Trả lời câu hỏi (tự do) | Speak | STT + task completion + fluency |
| Đóng vai | Speak | STT + 3 axes |

Free-text translation is **excluded from the MVP**. Grading it needs either LLM judging
at runtime (cost, latency, non-determinism) or huge accepted-answer lists. The word bank
bounds the answer space instead.

### 5.3 Sources by content type

The v6 rule was: generate scaffolding, never generate the source language.

| Content | Source | Notes |
|---|---|---|
| Example sentences per word | Tatoeba (CC-BY), VOA Learning English | Select by lemma match and level score. Tatoeba requires attribution on screen |
| Level 1–3 unit source | VOA *Let's Learn English* dialogues (public domain) | Real conversational scripts at A1–A2 |
| Level 4–7 unit source | VOA Learning English articles with audio (public domain) | Monologue passage. Speaking is question-answer, matching IELTS format |
| Word lists | Oxford 3000/5000, NGSL | |
| Audio | Kokoro-82M, generated in batch by the worker, stored in R2 | Multi-voice for dialogues, 0.8/1.0/1.15× |
| Distractors, VI glosses, grammar explanations, speaking questions | LLM draft → validator → review | Stored. Never generated live. No English source text is generated anywhere |

### 5.4 Source-first authoring (decided: option A everywhere → ADR-0006)

No English source text is generated, at any level. Reason: a solo project has no C1+
reviewer, so generated English cannot be quality-controlled.

Authoring runs **source → curriculum**, not the reverse:

1. Pick a VOA item for the topic and level. Levels 1–3 use a *Let's Learn English*
   dialogue. Levels 4–7 use a Learning English article with audio.
2. Extract target vocabulary: lemmas in the item that are at the level's frequency
   band and not already taught (tracked in the content graph).
3. Pick the grammar point: the first candidate for the level that the item actually
   contains, detected with the same spaCy patterns used in §7.3.
4. Generate only scaffolding around it: questions, distractors, glosses, explanations.

Consequences:
- Levels 4–7 have no roleplay. Speaking is IELTS-style question answering about the
  topic, which is the real exam format.
- Some topics will not be available at some levels. The curriculum follows the corpus.
- **Licensing check per item:** only text and audio credited to VOA staff. Wire-service
  content (AP, Reuters), third-party photos and embedded video are excluded. The
  pipeline stores the source URL and byline for each item.
- **Review is on the Vietnamese side only**, which the author can do as a native
  speaker: 100% of grammar explanations (8 per level) and 10% of exercises.

### 5.5 Pipeline

```
corpus → NFC → length filter → CEFR scoring → MinHash + bge-m3 dedup
       → lemma index (spaCy) → sentence picker per target word
       → LLM scaffolding (distractors, glosses, explanations)
       → validator (schema, answer key present, level check, banned-content check)
       → human review (100% VI grammar explanations, 10% exercises)
       → template expansion into exercises → Kokoro batch TTS → R2
```

v6 used LaBSE for bilingual filtering. v7 uses **bge-m3 cross-lingual cosine** instead,
because bge-m3 is already in the stack. It must be validated on 200 labelled Tatoeba
pairs before it replaces LaBSE. If it fails, add LaBSE back.

---

## 6. Duolingo mechanics: adopt or reject

| Mechanic | Decision | Reason |
|---|---|---|
| Path of units | Adopt | Clear next step, low decision fatigue |
| Short mixed-type lessons | Adopt | Core of the model |
| Streak + 1 streak freeze | Adopt | Highest retention per line of code. Day boundary is `Asia/Ho_Chi_Minh` |
| XP + daily goal | Adopt | Needed for the streak to mean something |
| Immediate per-exercise feedback | Adopt | Vietnamese, specific, never "Sai rồi!" |
| Personalised review | Adopt as **FSRS-5** | FSRS is open and benchmarked; Duolingo's HLR has no advantage for us |
| Hearts / energy | **Reject** | Punishing mistakes suppresses speaking attempts, and speaking is where learners make the most mistakes |
| Leagues | **Defer** | A league of 30 needs thousands of weekly actives. An empty leaderboard is worse than none |
| Gems, shop, mascot | **Reject** | Art and economy design cost with no learning value at our scale |
| Push reminders | Email first | Web push on iOS requires an installed PWA (iOS 16.4+). Most TikTok traffic will not install one |

Visual identity stays as defined in the design system: no green brand colour, no owl
lookalike, no copied path graphics. The mechanics can be copied. The trade dress
cannot.

---

## 7. AI features: how each works

### 7.1 Pronunciation (GOP): unchanged engine, much heavier use

`g2p_en` (ARPAbet) → **ARPAbet→espeak IPA mapping** → wav2vec2-lv-60-espeak ONNX (CPU)
→ CTC forced alignment → GOP per phoneme → calibrated thresholds (versioned).

- The substituted phoneme is the highest-posterior competitor in the aligned segment.
- The Vietnamese explanation comes from a hand-written lookup table keyed by
  `(expected, actual)`, such as `(θ, t) → "Đặt đầu lưỡi giữa hai hàm răng…"`. It uses
  no LLM: deterministic, free, reviewable.
- **New capacity risk.** v6 called GOP once per topic. v7 calls it about 15 times per
  unit, so CPU throughput on the VPS is now a launch concern (§10).

### 7.2 Fluency

Pure algorithms on the alignment or STT timestamps: words per minute, silence ratio,
hesitation count (filled pauses plus pauses > 0.5 s), and longest fluent run. No model.

### 7.3 Task completion

- STT transcript → spaCy `en_core_web_sm` (lemmas, POS, dependency parse).
- Vocabulary: lemma match against `targetVocab`.
- Grammar: `Matcher` / `DependencyMatcher` patterns per `grammarPoint`, stored with the
  grammar learnable, for example present perfect = `AUX(have) + VERB(VBN)`.
- spaCy is added to the stack because the v6 plan required syntactic matching but named
  no parser. The small model (~12 MB) runs in `speech-service` without a GPU.

### 7.4 Free speech (L6)

- STT uses Moonshine in dev and Groq Whisper in prod. **Transcription only**, never
  scoring.
- GOP on free speech takes the STT transcript as reference text. When STT mishears a
  badly pronounced word, GOP scores the wrong target. Mitigations:
  - Run GOP only on words whose STT confidence is ≥ threshold, plus the target
    vocabulary.
  - Keep a **separate eval gate**: Pearson r ≥ 0.5 on 100 labelled free-speech clips.
    If it fails, L6 shows fluency and task completion only.
- Levels 1–3 roleplay: the app plays the other speaker's lines from the VOA dialogue.
  The learner's turn is checked against the original line plus keyword/lemma intents.
  No runtime LLM, fully testable.
- Levels 4–7 (MVP is level 4): the app asks stored IELTS-style questions. The answer is
  scored on fluency and pronunciation, and task completion checks the unit's
  vocabulary and grammar. No roleplay partner is needed.

### 7.5 Placement test (after a second level exists)

Adaptive test, about 5 minutes, using Elo item difficulty over listen-select, dictation
and vocab items. It outputs a starting level, not a band.

### 7.6 LLM usage (ai-gateway)

- **Offline:** content scaffolding (§5.5), about $2–10 one-off per level.
- **Runtime at MVP: none.** Everything learners touch is deterministic or pre-generated.
- **Later:** speaking band estimation (gated per §3.2), LLM roleplay partner, agent
  tutor. Pydantic AI vs LangGraph remains open and blocks nothing until then.

---

## 8. Milestones

### M0 — Spike (blocks everything)
- [ ] **New:** inventory VOA — count usable items with audio per level and topic
- [ ] Domain `sonari.vn` / `sonari.app`, trademark classes 41 and 9
- [ ] Recruit 20 speakers × 10 sentences, written consent
- [ ] wav2vec2 spike: `bad.wav` must score differently from `good.wav`
- [ ] Forced-alignment spike: the `/θ/` segment sounds right
- [ ] **New:** ARPAbet→espeak mapping table and a test that round-trips 200 words
- [ ] Kokoro at 0.8/1.0/1.15× **plus a two-voice dialogue**
- [ ] **New:** CPU benchmark — GOP latency p50/p95 for a 3 s clip on the target VPS

### M1 — Foundation (unchanged from v6)
Repo, `CLAUDE.md`, Makefile, CI, Compose with Mongo replSet and Redis, auth with JWT
refresh rotation, OTel from day one.

### M2 — GOP scorer (unchanged)
Design A6 → freeze `ScoreResponse` → speech-service → 200-sample calibration → gate
Pearson r ≥ 0.6 (fallback: word-level) → `make test-speech` < 10 s.

### M3 — 🚀 Launch the standalone scorer
Same as v6, with copy switched to IELTS and practice sentences taken from level 4 unit
vocabulary. Target: 1000 consented audio samples. This feeds calibration and is the
data moat.

### M4 — Course engine, one vertical slice
- [ ] Content entities (§5.1) + event contracts
- [ ] Exercise engine: the 8 deterministic types + the 2 GOP types
- [ ] Path screen, unit screen, lesson player, lesson-complete screen
- [ ] FSRS-5 review mode, XP, daily goal, streak + freeze
- [ ] **Unit 3 (Đồ ăn, food and eating) built end to end by hand**
- Exit: one learner can complete unit 3 and see a review queue the next day

### M5 — Content pipeline + level 4
- [ ] Pipeline §5.5, template expansion, Kokoro batch
- [ ] Write ADR-0006 recording source-first authoring (§5.4)
- [ ] Per-item licensing filter (VOA byline, no wire content)
- [ ] Units 1–8 and Unit 0 through review
- [ ] Email streak reminder

### M6 — Speaking (L6)
- [ ] spaCy task-completion matcher + pattern library for 8 grammar points
- [ ] Fluency metrics
- [ ] IELTS-question speaking flow (level 4); scripted roleplay deferred until levels 1–3
- [ ] Free-speech GOP gate (§7.4)
- [ ] B18/B19 screens

### M7 — Eval + production
k3s, Grafana, CD, split to 3–4 processes, README, ADRs, demo video, blog posts,
cohort chart.

### Backlog (not planned)
Levels 1–3 and 5–7 · placement test · leagues · LLM roleplay partner · speaking band
estimate · agent tutor, MCP, RAG · reading · writing.

**Cut order when budget runs short:** optimization → agent → leagues and extra
gamification → extra levels.
**Never cut:** the basic eval harness, GOP calibration, streak/XP (core to the product
model).

---

## 9. Eval harness (built alongside, not in M7)

| Component | Metric | Gate |
|---|---|---|
| GOP, read speech | Pearson r vs human labels | ≥ 0.6 |
| GOP, free speech | Pearson r | ≥ 0.5, else hidden |
| STT on VN-accented English | WER | Recorded, and used to pick the confidence threshold |
| Task completion | Precision and recall on 100 labelled transcripts | P ≥ 0.9 (false "you didn't use X" hurts more than a miss) |
| ARPAbet→IPA map | Round-trip accuracy | 100% on the 200-word set |
| Content validator | Pass rate, review rejection rate | Tracked per batch |
| LLM judge (when added) | Cohen κ vs human | ≥ 0.6 before it gates CI |

---

## 10. Screens (delta from design-system)

- **Replaced:** B14 "lesson overview" (6-stage arc) becomes **B14 path** (levels and
  units) plus **B14b unit** (6 lessons with states).
- **New:** B20 lesson player shell (progress bar, exercise slot, check button, feedback
  sheet), B21 lesson complete (XP, streak), B22 streak/daily goal, B23 review session.
- **Kept:** A1–A9, B15 discover (now inside L5), B16 vocab card, B17 grammar explainer,
  B18 roleplay, B19 roleplay result.
- **Build order:** A6 → A4 → A3 → A1 → A7 → B20 → B14 → B14b → B16 → B17 → B21 → B18 →
  B19 → B22 → B23.

The design system's §5 "Lesson arc" needs rewriting to match §4 of this plan.

---

## 11. Budget

| | /month |
|---|---|
| VPS | $0–7 |
| LLM runtime | ~$0 at MVP (all offline) |
| STT (Groq) | < $1 at launch volume |
| R2 + Pages | $0 (audio for level 4 is well under the free 10 GB) |
| **Total** | **< $10** |

The binding constraint is **CPU for GOP**, not money. It is measured in M0.

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| GOP throughput too low on free VPS | M0 benchmark. Options: int8 ONNX quantisation, a queue with a UI "đang chấm" state, a cap on concurrent scoring |
| Free-speech GOP unreliable | Separate gate. Fall back to fluency + task completion |
| VOA lacks an item for a planned topic or level | Topic list is a candidate list. Swap topic, never generate text |
| The corpus supports exactly these 8 units with one reserve | The 8 units were confirmed by title only, and Films and TV (the reserve) sits exactly at the margin with no owner label. A unit that fails on close reading at M5 is replaced by Films and TV; a second failure leaves the course at **7 units**. Unit 0 has no passage and is unaffected. Read every chosen passage in full before building on it; the crawl keeps widening the pool |
| Non-public-domain content inside VOA pages | Byline filter, store source URL, exclude wire and third-party media |
| Content volume overwhelms solo dev | One level only. Template expansion. Manual review limited to Vietnamese explanations |
| Band claims mislead learners or draw complaints | §3.2 honesty rule and non-affiliation notice |
| Tatoeba attribution forgotten | Attribution field required by the validator. UI shows it on the sentence card |
| Scope creep toward "full Duolingo" | §6 table is the contract. New mechanics go to `docs/backlog.md` |

---

## 13. Decisions log (2026-09-29)

| Decision | Choice |
|---|---|
| Source of English text | Corpus only at every level, source-first authoring (§5.4, ADR-0006) |
| VSTEP | Dropped entirely. `examTags` stays in the schema for IELTS parts (P1/P2/P3) |
| MVP level | Level 4 (reference band 4.5–5.0) |
| Level scale | 7 difficulty levels; bands are content reference only (§3) |

## 14. Portfolio map (AI Engineer applications)

Each AI component shows a different skill, and **each has a measured number**. A skill
without a metric is a claim; with one it is evidence.

| Component | Skill shown | Evidence in README |
|---|---|---|
| GOP scorer | Speech ML, CTC alignment, calibration | Pearson r vs human labels, reliability plot |
| ONNX on CPU | Model serving, cost-aware inference | p50/p95 latency, before/after int8 |
| Content pipeline | LLM engineering: structured output, validators, batch | Validator pass rate, cost per 1000 items |
| Dedup + sentence picker | Embeddings, retrieval | Duplicate rate removed, precision on 100 picks |
| Task completion | Classical NLP (spaCy patterns) | Precision/recall on labelled transcripts |
| Eval harness + CI gate | Evaluation discipline | Gates that failed a build, and why |
| OTel + Langfuse | LLM observability | Trace screenshot, token cost dashboard |
| ADRs 0001/0004/0006 | Engineering judgement | Cost break-even, "why not generate text" |

Depth over breadth: the GOP engine and the eval harness are the two pieces to talk
about in an interview. The agent tutor stays in backlog. Adding it before eval exists
would show breadth without rigour.

## 15. Next session

1. Write ADR-0006.
2. Update `design-system.md` §5 and §6 to match §4 and §10.
3. Continue M0 — the wav2vec2 `good.wav` vs `bad.wav` spike is still the blocker.
