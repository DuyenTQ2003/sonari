# ADR-0009: The default trim cap is 10% of a passage's words

- Status: Accepted (maintainer's decision, 2026-10-04); supersedes decision 2 of ADR-0008 (the cap) and nothing else
- Date: 2026-10-04

## Context

ADR-0008 fixed the cap at 5% and said that changing it takes a superseding ADR. Its reason was risk: from 5%
to 10% a passage needs about twice as many lines cut (4.9 against 2.2), and the longer lines, where content hid
in the first reading, are what the extra words are made of. Two things have changed since. The lists are closed
(ADR-0008 5.3) and have been read: [voa-trim-corpus.md](../reports/voa-trim-corpus.md) reads every distinct
removed text in the 1,081 passages usable at 10% (531 texts, 2,646 lines) plus a random 300 lines and 150 long
texts of the whole corpus, and finds none wrong. And the maintainer wants more passages to choose from per unit.

What the data says about the choice: at 5% there are 724 usable passages (about 409 free of missed frame), at 10%
1,081 (about 674). Of the 357 passages that 10% adds, 255 are from programmes about English or from fiction,
which the units proposal ruled out as topical sources; 102 are topical. Every unit already has at least 28
usable passages at 5% (crude tags), against the 6 the proposal asks for, so the cap is not chosen for supply.

## Decision

1. **The default cap is 10%.** `make voa-trim` writes the passages usable at that cap.
2. **The cap is stored, not baked in.** Every record carries `trim.cap` and `trim.removed_share`, so the 5% set
   (or the 2% set) is a filter on the same file, with no second trim.
3. Everything else in ADR-0008 stands: whole lines only, provenance, the negative cases, the evidence a rule
   needs, and the 2% error gate.

## Consequences

- A wrong removal now costs more text: in the 10% set the median passage loses 2 lines and 2.9% of its words
  (p90: 4 lines, 7.2%); 73 removed lines are longer than 20 words, against 5 in the 5% set.
- **Trigger to go back to 5%:** one line of content found among the lines removed in a 5-10% passage. Raising the
  cap again, or removing it, is a superseding ADR with the table regenerated.
- The corpus is a filter away from the stricter set, so going back costs a query, not a re-run.

## Alternatives rejected

- **Stay at 5%.** Enough supply (about 409 passages free of missed frame against a need of about 50), and the
  safer reading of ADR-0008. Rejected by the maintainer for the choice of passages per unit, not for supply.
- **No cap.** The passages it adds are the ones whose frame is part of the text (ADR-0008).
