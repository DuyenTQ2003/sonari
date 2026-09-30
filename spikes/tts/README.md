# TTS spike (P05): Kokoro-82M for course audio

Question: is Kokoro-82M on CPU good enough for the course's listening audio? This spike
produces the audio and the speed numbers. Quality is judged by ear in
[`CHECKLIST.md`](CHECKLIST.md); the measurements are in [`RESULTS.md`](RESULTS.md).

## Texts (real VOA, nothing invented)

Both texts are quoted verbatim from VOA Learning English items whose byline is VOA
staff and which carry no AP/Reuters/AFP credit (checked by hand on 2026-09-30; P06
automates this check). They are stored with their metadata in [`texts.json`](texts.json).

| Use | Item | URL |
|---|---|---|
| One sentence, three speeds | *Words and Their Stories*: "'Watching the Grass Grow' Is Not Fun", 2025-03-15. "Anna Matteo wrote this story for VOA Learning English." | https://learningenglish.voanews.com/a/watching-the-grass-grow-is-not-fun/8003108.html |
| Six-turn dialogue, two voices | *Let's Learn English*, Level 2, Lesson 1: "Budget Cuts", 2019-05-12. Turns 1-6 of the Anna/Jonathan exchange. | https://learningenglish.voanews.com/a/lets-learn-english-level-2-lesson1/3960391.html |

The sentence has final consonant clusters on purpose ("plants", "end", "buds",
"shoots"): dropping final consonants is a typical problem for Vietnamese learners, so
audio that swallows them would teach the wrong model.

## Voices

`af_heart` for the sentence and for Anna; `am_michael` for Jonathan. Kokoro's
`speed` argument gives 0.8x, 1.0x and 1.15x.

## Run

```bash
uv run --directory spikes/tts python run_tts.py
```

The first run downloads the model (about 330 MB) and the spaCy model into the venv.
Audio goes to `DATA_DIR/derived/tts/` (default `~/sonari-data`), never into the repo.
From Windows the folder is `\\wsl$\<distro>\home\<user>\sonari-data\derived\tts`.

## Licences

Kokoro-82M: Apache-2.0. `en_core_web_sm` (spaCy): MIT. The two VOA excerpts are kept
only for this spike; ADR-0006 licence filtering applies to anything that reaches the
course.
