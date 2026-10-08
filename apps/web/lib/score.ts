// The speech service's answer (packages/contracts/schema/score-response.schema.json) and the few
// things the result view derives from it. Nothing here scores anything: the verdicts are the
// service's, and the view only shows them.
import { hasMessage, t } from "./messages";

export type Verdict = "correct" | "unclear" | "wrong";

export type Feedback = {
  messageKey: string;
  params: { expected: string; heard: string; word: string };
};

export type PhonemeScore = {
  expected: string;
  verdict: Verdict;
  heard: string | null;
  gop: number;
  startMs: number;
  endMs: number;
  feedback: Feedback | null; // set exactly when the verdict is "wrong"
};

export type WordScore = {
  text: string;
  start: number; // code points into referenceText
  end: number;
  verdict: Verdict; // the worst of its phonemes
  reference: "en-us" | "en-gb";
  correctPhonemes: number;
  phonemes: PhonemeScore[];
};

export type ScoreResponse = {
  thresholdsVersion: string;
  referenceText: string;
  words: WordScore[];
};

export type Piece =
  | { kind: "gap"; text: string }
  | { kind: "word"; index: number; word: WordScore };

/** The reference text cut into the scored words and the text between them (spaces, punctuation). */
export function pieces(result: ScoreResponse): Piece[] {
  const chars = Array.from(result.referenceText); // the service counts code points, not UTF-16 units
  const out: Piece[] = [];
  let at = 0;
  result.words.forEach((word, index) => {
    if (word.start > at) out.push({ kind: "gap", text: chars.slice(at, word.start).join("") });
    out.push({ kind: "word", index, word });
    at = Math.max(at, word.end);
  });
  if (at < chars.length) out.push({ kind: "gap", text: chars.slice(at).join("") });
  return out;
}

/**
 * The why and how text of a wrong phoneme. A key this app has no copy for gets the generic
 * explanation, which claims no cause, rather than an error or a blank.
 */
export function fixText(feedback: Feedback): { why: string; how: string } {
  const known = hasMessage(`${feedback.messageKey}.why`) && hasMessage(`${feedback.messageKey}.how`);
  const key = known ? feedback.messageKey : "pronunciation.fix.generic";
  return { why: t(`${key}.why`, feedback.params), how: t(`${key}.how`, feedback.params) };
}

/** The sentence index `delta` steps from `index`, wrapping around. */
export function step(index: number, delta: number, count: number): number {
  return (((index + delta) % count) + count) % count;
}

/** The raw response is for debugging: it shows only behind `?debug`. */
export function isDebug(search: string): boolean {
  return new URLSearchParams(search).has("debug");
}
