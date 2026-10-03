# Test data

## `nltk_data/corpora/cmudict/`: the CMU Pronouncing Dictionary, vendored

The tests of the real g2p backend (`tests/g2p/test_backend.py`) need the `cmudict` corpus in
`$DATA_DIR/nltk_data`. CI sets `DATA_DIR` to this directory, so it needs no download and no
network; a developer machine normally has its own copy under `~/sonari-data/nltk_data`.

- What: `cmudict.0.7a` as packaged by the NLTK data project (entries sorted for NLTK), the
  same files `python -m sonari_speech.g2p.backend` downloads. Both files are byte for byte as
  distributed; `tests/g2p/test_vendored_cmudict.py` checks their SHA-256:
  - `cmudict` `cad209c39eb87677d64e93d97f8eed10b7e6f9bdd42de8e7ca8efc8e17d62e8a` (3.8 MB, 133,737 lines)
  - `README` `b0556be7a2b12bea6a667277b75864f802dd4854480657ce298c62e6897e766b`
- Licence: Copyright (C) 1993-2008 Carnegie Mellon University. All rights reserved. A BSD-style
  licence (redistribution with or without modification, provided the copyright notice, the
  conditions and the disclaimer are kept). The full text is in the `README` next to the data,
  which must stay with it. The dictionary is a pronunciation lexicon, not English source text
  in the sense of ADR-0006.
- Why a copy and not a download: the tests must run in CI on every pull request, and a
  network fetch there would be a second way for the pipeline to break.
- The `end-of-file-fixer` and `trailing-whitespace` hooks skip this directory
  (`.pre-commit-config.yaml`): the `README` ends with a spare blank line and has one line of
  trailing spaces, and the files are kept as distributed.
- To refresh it: `python -m sonari_speech.g2p.backend /tmp/nltk`, copy
  `/tmp/nltk/corpora/cmudict/{cmudict,README}` here, and update the checksums above and in the test.
