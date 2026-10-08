// Score responses for the view tests. A builder, not hand-typed JSON, so that the derived fields
// (word verdict, correctPhonemes, character offsets, feedback only on "wrong") cannot drift;
// tests/result.test.tsx validates every fixture against the contract's JSON Schema.
import type { PhonemeScore, ScoreResponse, Verdict, WordScore } from "../lib/score";

/** [expected, verdict, heard (not for correct), fix rule (wrong only, default "generic")] */
export type P = [string, Verdict, string?, string?];

const GOP: Record<Verdict, number> = { correct: 2.5, unclear: -2, wrong: -7 };
const WORST: Verdict[] = ["wrong", "unclear", "correct"];

function phoneme([expected, verdict, heard = "ə", fix = "generic"]: P, word: string, at: number): PhonemeScore {
  return {
    expected,
    verdict,
    heard: verdict === "correct" ? null : heard,
    gop: GOP[verdict],
    startMs: at,
    endMs: at + 20,
    feedback:
      verdict === "wrong"
        ? { messageKey: `pronunciation.fix.${fix}`, params: { expected, heard, word } }
        : null,
  };
}

/** `words` are [text, phonemes]; each is found in `text` after the previous one. */
export function response(text: string, words: [string, P[]][]): ScoreResponse {
  let from = 0;
  let at = 0;
  const scored = words.map(([word, phonemes]): WordScore => {
    const start = Array.from(text.slice(0, text.indexOf(word, from))).length;
    from = text.indexOf(word, from) + word.length;
    const rows = phonemes.map((p) => phoneme(p, word, (at += 40)));
    return {
      text: word,
      start,
      end: start + Array.from(word).length,
      verdict: WORST.find((v) => rows.some((r) => r.verdict === v)) ?? "unclear",
      reference: "en-us",
      correctPhonemes: rows.filter((r) => r.verdict === "correct").length,
      phonemes: rows,
    };
  });
  return { thresholdsVersion: "v2-native-s20261008-val20261009", referenceText: text, words: scored };
}

export const ALL_CORRECT = response("One think you.", [
  ["One", [["w", "correct"], ["ʌ", "correct"], ["n", "correct"]]],
  ["think", [["θ", "correct"], ["ɪ", "correct"], ["ŋ", "correct"], ["k", "correct"]]],
  ["you", [["j", "correct"], ["uː", "correct"]]],
]);

// All three verdicts, two words with a wrong phoneme (a rule with copy and another),
// one with only an unclear one.
export const MIXED = response("Thank you very much.", [
  ["Thank", [["θ", "wrong", "t", "th_stop"], ["æ", "correct"], ["ŋ", "unclear", "n"], ["k", "correct"]]],
  ["you", [["j", "correct"], ["uː", "correct"]]],
  ["very", [["v", "unclear", "b"], ["ɛ", "correct"], ["ɹ", "correct"], ["i", "correct"]]],
  ["much", [["m", "correct"], ["ʌ", "correct"], ["tʃ", "wrong", "t", "final_consonant"]]],
]);

export const ALL_UNCLEAR = response("Good morning.", [
  ["Good", [["ɡ", "unclear", "k"], ["ʊ", "unclear", "ə"], ["d", "unclear", "t"]]],
  ["morning", [["m", "unclear", "n"], ["ɔː", "unclear", "ɑː"], ["n", "unclear", "m"], ["ɪ", "unclear", "i"], ["ŋ", "unclear", "n"]]],
]);

// P02's gate case: the /t/ of "tink" heard as /θ/ (generic: that pair has no rule).
export const WRONG_WITH_FEEDBACK = response("One tink you.", [
  ["One", [["w", "correct"], ["ʌ", "correct"], ["n", "correct"]]],
  ["tink", [["t", "wrong", "θ"], ["ɪ", "correct"], ["ŋ", "correct"], ["k", "correct"]]],
  ["you", [["j", "correct"], ["uː", "correct"]]],
]);

export const FIXTURES = { ALL_CORRECT, MIXED, ALL_UNCLEAR, WRONG_WITH_FEEDBACK };
