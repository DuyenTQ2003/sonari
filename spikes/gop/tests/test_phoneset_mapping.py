from phoneset.check_vocab import missing_tokens
from phoneset.mapping import mapped_tokens

# The mapping itself is tested in services/speech/tests/phoneset/test_mapping.py (P21).


def test_missing_tokens_reports_what_the_vocab_lacks() -> None:
    vocab = {tok: i for i, tok in enumerate(mapped_tokens())}
    assert missing_tokens(vocab) == []
    del vocab["ɔːɹ"]
    assert missing_tokens(vocab) == ["ɔːɹ"]
