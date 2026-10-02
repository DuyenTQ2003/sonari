"""Words with the ARPAbet that g2p_en returns for them and the espeak tokens expected."""

# (word, CMUdict ARPAbet as g2p_en returns it, expected espeak tokens). The first eight are
# the hand-written tokens of the P02 spike; the rest cover every mapping fix of P03.
WORDS = [
    ("think", "TH IH1 NG K", "θ ɪ ŋ k"),
    ("three", "TH R IY1", "θ ɹ iː"),
    ("thank", "TH AE1 NG K", "θ æ ŋ k"),
    ("thought", "TH AO1 T", "θ ɔː t"),
    ("tin", "T IH1 N", "t ɪ n"),
    ("took", "T UH1 K", "t ʊ k"),
    ("talk", "T AO1 K", "t ɔː k"),
    ("time", "T AY1 M", "t aɪ m"),
    ("happy", "HH AE1 P IY0", "h æ p i"),  # unstressed IY, word-final
    ("create", "K R IY0 EY1 T", "k ɹ iː eɪ t"),  # unstressed IY before a vowel
    ("anything", "EH1 N IY0 TH IH2 NG", "ɛ n ɪ θ ɪ ŋ"),  # unstressed IY before a consonant
    ("car", "K AA1 R", "k ɑːɹ"),  # vowel + R is one token
    ("near", "N IH1 R", "n ɪɹ"),
    ("very", "V EH1 R IY0", "v ɛ ɹ i"),  # ... but not before a vowel
    ("during", "D UH1 R IH0 NG", "d ʊɹ ɹ ɪ ŋ"),  # UH doubles the r
    ("here", "HH IY1 R", "h ɪɹ"),  # CMUdict spells the NEAR set IY R
    ("fire", "F AY1 ER0", "f aɪɚ"),  # AY + ER0
    ("retire", "R IH0 T AY1 R", "ɹ ɪ t aɪɚ"),  # AY + R
    ("science", "S AY1 AH0 N S", "s aɪə n s"),  # AY + AH0
    ("area", "EH1 R IY0 AH0", "ɛ ɹ iə"),  # IY + AH0
    ("idea", "AY0 D IY1 AH0", "aɪ d iə"),
    ("around", "ER0 AW1 N D", "ɚ ɹ aʊ n d"),  # ER before a vowel is followed by r
    ("current", "K ER1 AH0 N T", "k ɜː ɹ ə n t"),
    ("about", "AH0 B AW1 T", "ə b aʊ t"),  # unstressed AH is schwa
    ("choice", "CH OY1 S", "tʃ ɔɪ s"),  # affricate and diphthong are single tokens
    ("teacher", "T IY1 CH ER0", "t iː tʃ ɚ"),
    ("joke", "JH OW1 K", "dʒ oʊ k"),
    ("city", "S IH1 T IY0", "s ɪ t i"),  # t stays t, never the flap
    ("water", "W AO1 T ER0", "w ɔː t ɚ"),
    ("little", "L IH1 T AH0 L", "l ɪ t ə l"),
    ("because", "B IH0 K AO1 Z", "b ɪ k ɔː z"),  # accent variant: CMUdict's first form stays
]
