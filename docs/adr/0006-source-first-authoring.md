# ADR-0006: Source-first authoring, no generated English

- Status: Accepted
- Date: 2026-09-29

## Context

Each unit needs an English source text: a dialogue (levels 1–3) or a passage
(levels 4–7). From that text the unit teaches 12 words and one grammar point, and
the learner is then scored on whether they use them.

Three options were considered:

- **A. Corpus only.** Take real text first and derive the curriculum from it.
- **B. Constrained generation.** An LLM drafts text that contains the target words
  and grammar, and a C1+ human reviews 100% of it.
- **C. Hybrid.** A for levels 1–3, B for levels 4–7.

B and C require a C1+ English reviewer. This is a solo project with no such reviewer,
so generated English cannot be quality-controlled. Fluent-but-unnatural phrasing
would be taught as a model to learners.

## Decision

Option A at every level.

1. Pick a VOA item for the topic and level. Levels 1–3 use *Let's Learn English*
   dialogues. Levels 4–7 use Learning English articles with audio.
2. Target vocabulary = lemmas in the item at the level's frequency band, not yet
   taught.
3. Grammar point = the first candidate for the level that the item contains, detected
   with spaCy patterns.
4. The LLM generates scaffolding only: questions, distractors, Vietnamese glosses,
   grammar explanations.
5. Example sentences per word come from Tatoeba or VOA, never from an LLM.

## Consequences

- Levels 4–7 have no roleplay. Speaking is IELTS Part 1/2/3-style question answering,
  which matches the real exam format.
- Topic lists become candidate lists. If no item fits, swap the topic; never write
  text.
- Each item passes a licensing filter. Only VOA-staff bylines are accepted; wire
  content and third-party media are excluded. Source URL and byline are stored.
- Human review covers only the Vietnamese side, which the author can do as a native
  speaker: 100% of grammar explanations and 10% of exercises.
- The corpus inventory in M0 becomes a blocking task. How many usable VOA items exist
  per level decides the curriculum size.
