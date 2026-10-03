"""Re-export of the ARPAbet -> espeak mapping, which moved to the speech service (P21).

The spike keeps importing `phoneset.mapping`; the table and the code live in
services/speech/src/sonari_speech/phoneset/ so that there is one copy. Only PyYAML is
needed, so this works in the spike venv and in `make test-tools` alike.
"""

import sys
from pathlib import Path

_SERVICE_SRC = Path(__file__).resolve().parents[3] / "services" / "speech" / "src"
if str(_SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(_SERVICE_SRC))

from sonari_speech.phoneset.mapping import (  # noqa: E402
    TABLE_PATH,
    VOWELS,
    load_table,
    mapped_tokens,
    split_stress,
    to_espeak,
)

__all__ = ["TABLE_PATH", "VOWELS", "load_table", "mapped_tokens", "split_stress", "to_espeak"]
