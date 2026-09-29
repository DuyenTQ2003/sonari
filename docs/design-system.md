# Design System & Screen Inventory

Product name: **Sonari** (lowercase `sonari` in the wordmark).
Positioning EN: *Topic-based IELTS listening and speaking, scored down to the phoneme.*
Positioning VI: *Luyện nghe nói IELTS theo chủ đề, chấm phát âm đến từng âm.*

## Language

All UI copy shown to learners is Vietnamese and lives in
`apps/web/messages/vi.json`. Component names, props, comments, and this document are
English. Prompts sent to design tools are English; the copy they produce is Vietnamese.

---

## 1. Tokens

```css
/* Brand */
--brand-600: #5B4FE9;   /* primary buttons, headings */
--brand-500: #7A70F0;
--brand-100: #ECEAFE;   /* subtle emphasis background */
--accent-500:#FF6B4A;   /* secondary CTA, streak, badges */

/* Semantic — pronunciation scoring ONLY, never brand usage */
--good-500:  #16A97A;
--ok-500:    #F5A524;
--bad-500:   #E5484D;

/* Text and surface */
--ink-900:    #10162F;
--ink-500:    #5A6180;
--surface:    #FFFFFF;
--surface-alt:#FBFAFF;
--border:     #E8E6F5;
```

**Never use green as a brand colour.** That is Duolingo's identity. Green appears only
as the semantic "good" state.

## 2. Typography

| Role | Font | Reason |
|---|---|---|
| All text | **Be Vietnam Pro** | Designed for Vietnamese — diacritics do not collide with capitals or get clipped. Vietnamese readers notice when a font gets this wrong. |
| IPA symbols | **Charis SIL** or **Doulos SIL** | Most commonly missed detail. Many web fonts lack `/θ/ /ð/ /ʃ/ /ʒ/ /ŋ/ /æ/ /ɪ/ /ʊ/ /ɜː/` and render tofu boxes. Displaying IPA *is* the product. |
| Score numerals | Be Vietnam Pro, `font-variant-numeric: tabular-nums` | Digits must not jump between 99 and 100 |

Scale: 12 / 14 / 16 / 20 / 24 / 32 / 48. Body 16px, floor 14px.

## 3. Components and motion

- Radii: `8px` chips and badges, `12px` inputs and small cards, `20px` large cards
  and modals
- Spacing on a 4px grid. Standard padding 16px, section gap 24px
- Two shadow levels only: card `0 1px 3px rgba(16,22,47,.08)`, modal
  `0 12px 32px rgba(16,22,47,.16)`
- Motion: 150ms interaction, 250ms transition, 400ms celebration,
  `cubic-bezier(.2,.8,.2,1)`
- **Mobile-first at 390px.** Traffic arrives from TikTok; assume a phone
- Touch targets ≥44px. The record button is 72px
- **Colour is never the sole information channel.** A wrong phoneme carries colour,
  a wavy underline, and a text label. This is accessibility, not decoration

## 4. Copy voice (Vietnamese)

- Address the user as **"bạn"**
- Short sentences, no trailing ellipses
- On errors, describe the specific problem rather than judging
  - Good: `Âm /θ/ đang thành /t/ — thử đặt lưỡi giữa hai hàm răng`
  - Bad: `Sai rồi!`
- No emoji outside celebration screens

---

## 5. Course structure — the product's spine

Duolingo-style path. See `PLAN-v7.md` §4 for the full rules.

```
Level 1..7                 teaching difficulty (MVP: level 4)
└── Unit = one topic       built around one real VOA source (ADR-0006)
    ├── L1 Vocabulary A    6 words
    ├── L2 Vocabulary B    6 words
    ├── L3 Sentences       the 12 words inside real sentences
    ├── L4 Grammar         1 point, contrastive VI explanation
    ├── L5 Listening       the unit source (dialogue lv 1–3, passage lv 4–7)
    └── L6 Speaking        roleplay (lv 1–3) or IELTS-style questions (lv 4–7)
Review                     separate FSRS mode, daily
```

A lesson is 10–15 mixed exercises and takes about 5 minutes. Items enter FSRS only
after they have been taught in L1–L4.

L6 scores three axes:
- **Pronunciation**: GOP, per phoneme.
- **Fluency**: words per minute, silence ratio, hesitation count, longest run.
  Pure algorithms.
- **Task completion**: did the learner use the unit's target vocabulary and grammar?
  Lemma matching plus spaCy pattern matching.

Gamification is **streak (with one freeze), XP, and a daily goal** only. There are no
hearts, leagues, gems or mascot. Streak and XP use `--accent-500`, never green.

Levels are shown as **"Cấp 4"**, optionally "(tương đương band 4.5–5.0)". Never write
"Bạn đạt band X".

---

## 6. Screen inventory

### Group A — Launch (9). Standalone scorer.

| # | Screen | Note |
|---|---|---|
| A1 | Landing | One CTA: try without signing up |
| A2 | Sentence picker | Five sentences with IPA |
| A3 | Ready to record | 72px mic button |
| A4 | Recording | Live waveform, timer, stop |
| A5 | Scoring | Skeleton, 1–2 s |
| A6 | **Result** | Score, per-phoneme breakdown, fixes. **Most important screen** |
| A7 | Share card | 1200x630 OG image |
| A8 | Sign up / log in | Modal, only after a result exists |
| A9 | Errors and permissions | Mic blocked, no mic, network. iOS Safari blocks often |

### Group B — Course (MVP, level 4)

| # | Screen | Note |
|---|---|---|
| B14 | **Path** | Levels and units, current unit highlighted |
| B14b | **Unit** | 6 lessons with states, unit goal at the end |
| B15 | Listening (L5) | Source audio, hidden transcript, gist + detail questions |
| B16 | Vocabulary card | Headword, IPA, meaning, corpus example sentence with attribution |
| B17 | Grammar explainer | Contrastive VI explanation, lines from the unit source |
| B19 | **Speaking result** | Three axes, target words used/missed, sounds to fix |
| B20 | **Lesson player** | Shell: progress bar, exercise slot, check button, feedback sheet |
| B21 | Lesson complete | XP gained, streak state |
| B22 | Streak and daily goal | Calendar strip, freeze status |
| B23 | Review session | FSRS queue in the lesson player shell |
| B24 | **Speaking question** | IELTS Part 1-style question, record answer, target-word hints |

Exercise types rendered inside B20: listen-select meaning, listen-select word, match
pairs, word-bank sentence, VI→EN word bank, fill blank, dictation, read aloud, and
listen-and-repeat.

### Deferred

B18 Roleplay (levels 1–3 only, not MVP) · onboarding · placement test · agent · admin.

**Build order:** A6 → A4 → A3 → A1 → A7 → B20 → B14 → B14b → B16 → B17 → B24 → B19 →
B21 → B15 → B22 → B23

A6 comes first because it determines the `ScoreResponse` contract. B20 comes before
B14 because every lesson and review renders inside it.

---

## 7. Prompts for AI design tools

Works with v0.dev, Lovable, Bolt.new, Figma Make, Google Stitch, Uizard.
Send the base prompt once per session, then one screen per message. If the tool does
not keep context between messages, re-paste the token block each time.

### 7.0. Base prompt

```
Build a mobile-first web app UI in React + TypeScript + TailwindCSS.
Use only core Tailwind utility classes. No UI kit beyond shadcn/ui.

PRODUCT
"Sonari" — Duolingo-style, topic-based IELTS listening and speaking course for
Vietnamese university students.
Signature feature: phoneme-level pronunciation scoring that shows exactly which
sound was wrong and which sound replaced it, explained in Vietnamese.

DESIGN TOKENS — follow exactly, no substitutions
brand:   #5B4FE9  #7A70F0  #ECEAFE       accent: #FF6B4A
semantic (pronunciation verdicts ONLY, never brand usage):
         good #16A97A   ok #F5A524   bad #E5484D
text:    #10162F primary   #5A6180 secondary
surface: #FFFFFF   #FBFAFF              border: #E8E6F5

NEVER use green as a brand colour. Green appears only as the "good" verdict.

TYPE
"Be Vietnam Pro" for all text. "Charis SIL" for IPA symbols only.
Scale 12/14/16/20/24/32/48. Body 16px, never below 14px.
Score numerals use font-variant-numeric: tabular-nums.

SHAPE & MOTION
Radius 8px chips, 12px inputs, 20px large cards. Spacing on a 4px grid.
Card padding 16px, section gap 24px.
Shadows: card 0 1px 3px rgba(16,22,47,.08); modal 0 12px 32px rgba(16,22,47,.16)
Transitions 150ms interaction, 250ms navigation, cubic-bezier(.2,.8,.2,1)

HARD CONSTRAINTS
1. Mobile-first at 390px. Desktop is an expanded state, not the default.
2. Touch targets at least 44px. The microphone button is 72px.
3. Colour is NEVER the only information channel. A mispronounced phoneme carries
   colour AND a wavy underline AND a text label. Functional accessibility
   requirement, not a style preference.
4. Render all five states where relevant: idle, loading, empty, error, success.
5. No browser storage APIs. React state only.

COPY
All user-facing text is VIETNAMESE. Address the user as "bạn". Short sentences.
When the learner is wrong, describe the specific problem instead of judging.
  Good: "Âm /θ/ đang thành /t/ — thử đặt lưỡi giữa hai hàm răng"
  Bad:  "Sai rồi!"
No emoji except on celebration screens.

Reply "ready" and wait. I will send one screen per message.
```

### 7.1. A6 — Pronunciation result (design this first)

```
Screen: PRONUNCIATION RESULT, mobile 390px.

Top to bottom:
1. Overall score as a circular progress ring, 48px numeral centred, ring colour
   from the semantic scale, short Vietnamese label underneath.
2. The sentence just read, 20px. EACH WORD tinted by its verdict. Wrong words
   also get a wavy underline, not only a colour change.
3. Phoneme strip: the sentence's IPA sequence, each symbol a small chip tinted
   by verdict, tappable to open detail.
4. "Âm cần sửa" cards, maximum three. Each has a large IPA symbol on the left,
   a line reading "Bạn đang đọc thành /t/", one sentence of Vietnamese
   articulation guidance, and a play button for reference audio.
5. Two buttons: "Thử lại" (outline) and "Chia sẻ kết quả" (filled, brand).
6. Soft bottom strip prompting sign-up to save progress.

The learner must understand which sound they got wrong within three seconds.
```

### 7.2. A4 — Recording state

```
Screen: RECORDING state, mobile 390px.

- Target sentence at top, 24px, smaller IPA beneath in #5A6180
- Centre: live waveform, amplitude following input level, brand colour
- 72px mic button in active state with a pulsing ring
- Seconds counter below, clear stop button
- Hint line: "Đọc tự nhiên, không cần đọc chậm"

Visual feedback must be immediate — the user needs to know the mic is live.
```

### 7.3. A7 — Share card

```
Design a SHARE CARD, 1200x630, for Facebook and TikTok.

- Deep brand-violet gradient background
- Very large score in the centre
- Below: the sentence read, plus three highlighted IPA chips
- Bottom corner: lowercase "sonari" wordmark and
  "Kiểm tra phát âm miễn phí tại sonari.vn"
- Must stay legible when scaled to 300px wide in a feed

Goal: someone scrolling past should want to test themselves.
```

### 7.4. B14 — Path and B14b — Unit

```
Screen: LEARNING PATH, mobile 390px.

Header: level chip "Cấp 4", small reference text "tương đương band 4.5–5.0",
streak counter (flame icon, accent colour) and daily-goal ring on the right.

Body: a vertical path of unit nodes, one per topic, connected by a line.
Each node: a 64px circle with a topic icon, the Vietnamese topic name beneath
("Đồ ăn & nhà hàng"), and a state:
  completed   — check badge, muted
  current     — brand fill, pulsing ring, "Bắt đầu" tooltip
  locked      — lock icon, reduced opacity
States must be distinguishable without colour.

Bottom: tab bar with "Học", "Ôn tập", "Hồ sơ".
Do not imitate Duolingo's mascot, green palette or zig-zag path shape.
```

```
Screen: UNIT, mobile 390px.

Header: topic title "Đồ ăn & nhà hàng", "Cấp 4", unit progress bar.

Body: 6 lesson rows in order:
  1. Từ vựng 1      "6 từ mới"
  2. Từ vựng 2      "6 từ mới"
  3. Câu vận dụng   "Dùng từ trong câu thật"
  4. Ngữ pháp       "Danh từ đếm được / không đếm được"
  5. Nghe           "Bài nghe VOA"
  6. Nói            "Trả lời câu hỏi kiểu IELTS Part 1"
Each row: 44px icon, name, one-line description, "~5 phút", state
(completed with score chip / current / available / locked with "Hoàn thành bài trước").
Lesson 6 is visually emphasised as the unit goal.

Bottom: sticky "Tiếp tục" jumping to the current lesson.
Show lessons 1–2 completed, 3 current, 4–6 locked.
```

### 7.4b. B20 — Lesson player

```
Screen: LESSON PLAYER shell, mobile 390px.

Top: close button, thin progress bar (7/12), no hearts or lives.
Centre: exercise slot. Render one example: "Nghe và chọn nghĩa đúng" — a
speaker button (replay, and a slow 0.8x button), four Vietnamese meaning
options as large tappable cards.
Bottom: full-width "Kiểm tra" button, disabled until an option is chosen.

Feedback sheet slides up after checking:
  correct — check icon + "Chính xác", the English word with IPA, "Tiếp tục"
  wrong   — cross icon + the correct answer, one Vietnamese sentence explaining
            the specific problem (never "Sai rồi!"), "Tiếp tục"
Icons and labels carry the verdict, not colour alone.

Also produce the read-aloud variant: target sentence with IPA, 72px mic button,
and a result sheet showing per-word verdicts from A6.
```

### 7.5. B18 — Roleplay (deferred: levels 1–3 only)

```
Screen: ROLEPLAY CONVERSATION, mobile 390px.

The learner plays "khách hàng" in a restaurant ordering dialogue; the app plays
"nhân viên".

Top bar: scenario title "Gọi món ở nhà hàng", turn counter "Lượt 3/8", exit
button, thin progress bar.

Body: chat-style transcript, newest turn at the bottom.
  App turns: left-aligned bubble, surface-alt background, small speaker button
  to replay audio, "Xem nghĩa" toggle revealing the Vietnamese translation.
  Completed learner turns: right-aligned brand-tinted bubble showing the
  transcript with per-word verdict tinting and wavy underlines on mispronounced
  words, plus a small score chip.

Current turn, pinned above the bottom bar:
  A hint card showing target vocabulary as chips — "recommend", "allergic",
  "separate check". Chips already used appear checked and muted.
  An optional "Gợi ý câu" button revealing a suggested sentence.

Bottom bar: 72px microphone button centred, pulsing ring while recording, live
waveform, seconds counter. A smaller "Bỏ qua lượt này" text button to the right.

Also produce the RECORDING and PROCESSING states of this same screen.
```

### 7.6. B19 — Speaking result

```
Screen: SPEAKING RESULT (end of lesson 6), mobile 390px.

Top: overall score in a circular ring, 48px numeral, short Vietnamese label.

Then THREE horizontal score bars, each with a label, a value, and one line of
Vietnamese explanation:
  1. Phát âm      — "Phát âm rõ, còn 2 âm cần sửa"
  2. Trôi chảy    — "Tốc độ 98 từ/phút, hơi nhiều khoảng lặng"
  3. Hoàn thành   — "Bạn dùng được 7/10 từ mục tiêu"

Then a "Từ mục tiêu" card: chips for every target word in two labelled rows,
"Đã dùng" and "Chưa dùng". Used chips are checked and tinted good; missed chips
are outlined, tinted bad, each with a small speaker button. Label the rows — do
not rely on chip colour alone.

Then a "Cấu trúc ngữ pháp" card with the same treatment for the lesson's target
grammar patterns.

Then "Âm cần sửa", maximum 3 cards, same layout as screen A6.

Bottom: "Nói lại" (outline) and "Hoàn thành bài học" (filled).

The learner must see within three seconds which of the three axes is weakest.
```

### 7.7. B16 — Vocabulary card

```
Screen: VOCABULARY CARD, mobile 390px, part of a swipeable deck.

Top to bottom:
  - progress "4 / 12" and a thin bar
  - English headword, 32px
  - IPA beneath in secondary colour using the IPA font, with a speaker button
  - part-of-speech chip and CEFR chip
  - Vietnamese meaning, 20px
  - an English example sentence with the headword highlighted, Vietnamese
    translation in secondary text beneath
  - "Luyện phát âm" secondary button with a mic icon, opening the drill

Bottom bar: three spaced-repetition responses — "Chưa thuộc" / "Còn phân vân" /
"Đã thuộc" — evenly spaced, each at least 44px tall, each with a distinct icon
so they are not distinguished by colour alone.

Also produce the post-answer variant showing "lần ôn tiếp theo: 2 ngày".
```

### 7.8. B17 — Grammar explainer

```
Screen: GRAMMAR EXPLAINER, mobile 390px.
Its entire purpose is contrastive explanation for Vietnamese speakers.

Top: the pattern as a heading, e.g. "Would you like ...?", with a one-line
Vietnamese summary of when to use it.

Then a "Vì sao người Việt hay sai" card on a brand-tinted background:
  - a crossed-out incorrect sentence: "I want a coffee."
  - a corrected sentence: "Could I have a coffee, please?"
  - two or three Vietnamese sentences explaining the interference: Vietnamese
    marks politeness differently, so a direct translation of "tôi muốn" lands
    as blunt in English.
  Mark correct and incorrect with icons and labels, not only colour.

Then a "Cấu trúc" card showing the pattern with highlighted slots, e.g.
"Would you like + [danh từ / to + động từ] ?", with two or three filled examples.

Then a "Trong đoạn hội thoại" card quoting the two lines from this lesson's
dialogue where the pattern appears, each with a speaker button.

Bottom: sticky "Làm bài tập" primary button.
```

### 7.9. B15 — Listening (lesson 5)

```
Screen: DISCOVER — listen to the target dialogue, mobile 390px.

Top: Vietnamese scenario title and an instruction line:
"Nghe một lần. Chưa cần hiểu hết."

Centre: an audio player card — large play/pause button, scrubbable progress bar
with elapsed and total time, speed control offering 0.8x, 1.0x, 1.15x.

Below: a transcript area HIDDEN by default behind a "Hiện lời thoại" toggle.
When shown, each turn is a row with speaker role, English line, and a per-line
speaker button. Vietnamese translation appears only behind a second toggle
"Hiện nghĩa tiếng Việt".

Below that: two gist multiple-choice questions in Vietnamese, 3 options each.
These check overall understanding, not detail.

Bottom: sticky "Tiếp tục" button, disabled until the audio has played once.
```

### 7.10. B24 — Speaking question

```
Screen: SPEAKING QUESTION (lesson 6, level 4), mobile 390px.

Top: "Câu 2/4", close button, progress bar.
Question card: English question in 20px ("What kind of food do you usually
eat?"), speaker button to hear it, a "Xem nghĩa" toggle for the Vietnamese
translation.
Hint card: target vocabulary chips from this unit; chips used in earlier answers
appear checked and muted. Target grammar pattern shown as one line,
e.g. "some / any + danh từ".
Guidance line: "Trả lời 2–3 câu. Không cần hoàn hảo."

Bottom: 72px mic button, live waveform, seconds counter with a soft target of
20–30 s, "Bỏ qua" text button.
Also produce RECORDING and PROCESSING states.
```
