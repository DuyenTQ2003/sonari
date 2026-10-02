# sonari-speech

Speech service: reference text to expected phonemes, then (P20+) audio decoding, alignment
and GOP scoring. No torch: ONNX runtime and numpy only.

## Reference pronunciation (P21)

```python
from sonari_speech.g2p import G2pEnBackend, Pronouncer

pronouncer = Pronouncer(G2pEnBackend())  # loads g2p_en once, about 2 s
pronouncer.pronounce("I don't think so")
# -> one WordPron per word: text, start/end span in the reference, ARPAbet,
#    espeak tokens, and where they came from (lexicon, dictionary, contraction, predicted, number)
```

Lookup order per word: `g2p/lexicon.yaml` (overrides) → CMUdict → stem plus clitic for
contractions CMUdict lacks → g2p_en's neural guess. Digits are read out ("24" is one word
for the UI, "twenty four" for the model). ARPAbet becomes espeak tokens through
`phoneset/arpabet_to_espeak.yaml` (the P03 table, moved here from `spikes/gop`).

- A sentence takes 0.1-0.2 ms when every word is in CMUdict, about 1 ms per unknown word (the
  neural guess); measured 2026-10-03 on the laptop, budget 10 ms.
- Homographs ("read", "live") take CMUdict's first variant; there is no POS disambiguation.
- Adding a lexicon entry: give `arpabet`, the `espeak` tokens espeak-ng gives and a `why`; the
  tests check that the table maps the first to the second.

### NLTK data

The backend needs the `cmudict` corpus in `$DATA_DIR/nltk_data` (default `~/sonari-data`).
It never downloads at runtime: it raises `G2pDataMissing`, and importing g2p_en runs with
`nltk.download` disabled. Fetch it once, at build time:

```bash
uv run --directory services/speech python -m sonari_speech.g2p.backend
```

Without the data, the 35 tests that use the real backend skip (as they do in CI today); the
rest run against a fake backend.
