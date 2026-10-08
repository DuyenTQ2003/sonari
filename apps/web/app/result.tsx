// The learner's result: the sentence word by word, and for the word they pick, its phonemes.
// Pure view (no hooks, no fetch): the page owns which word is selected. Three rules from the
// brief: a word with a "wrong" phoneme needs work; "unclear" is shown neutrally and is never an
// error (the model is not sure); no percentage and no overall score (the thresholds are
// calibrated on native speakers only, and a number would imply precision the system lacks).
import { t } from "../lib/messages";
import {
  fixText,
  pieces,
  type Feedback,
  type PhonemeScore,
  type ScoreResponse,
  type Verdict,
  type WordScore,
} from "../lib/score";

export const CARD = "rounded-lg bg-white p-4 text-xl leading-loose shadow";
export const DETAIL_ID = "word-detail";

// Verdicts differ in shape, not only in colour: the underline of a word, the glyph and the label
// of a phoneme. Colour (TONE) is only a second cue; tests pin that SHAPE and GLYPH never repeat.
export const SHAPE: Record<Verdict, string> = {
  correct: "no-underline",
  unclear: "underline decoration-dotted decoration-2 underline-offset-4",
  wrong: "underline decoration-solid decoration-2 underline-offset-4 font-semibold",
};
export const GLYPH: Record<Verdict, string> = { correct: "✓", unclear: "~", wrong: "✗" };
const TONE: Record<Verdict, string> = {
  correct: "text-slate-900",
  unclear: "text-slate-700 decoration-slate-500",
  wrong: "text-rose-800 decoration-rose-600",
};
const LABEL: Record<Verdict, string> = {
  correct: "practice.verdict.correct",
  unclear: "practice.verdict.unclear",
  wrong: "practice.verdict.wrong",
};
const LEGEND: Record<Verdict, string> = {
  correct: "practice.legend.correct",
  unclear: "practice.legend.unclear",
  wrong: "practice.legend.wrong",
};
const ORDER: Verdict[] = ["wrong", "unclear", "correct"];

type Props = {
  result: ScoreResponse;
  selected: number | null; // index into result.words
  onSelect: (index: number | null) => void;
};

function WordButton({ word, selected, onClick }: { word: WordScore; selected: boolean; onClick: () => void }) {
  const ring = selected ? "bg-slate-100 ring-2 ring-slate-800" : "hover:bg-slate-100";
  return (
    <button
      type="button"
      data-verdict={word.verdict}
      aria-pressed={selected}
      aria-controls={selected ? DETAIL_ID : undefined}
      onClick={onClick}
      className={`cursor-pointer rounded px-0.5 ${SHAPE[word.verdict]} ${TONE[word.verdict]} ${ring}`}
    >
      {word.text}
      <span lang="vi" className="sr-only">
        {` (${t(LABEL[word.verdict])})`}
      </span>
    </button>
  );
}

function Fix({ feedback }: { feedback: Feedback }) {
  const { why, how } = fixText(feedback);
  return (
    <div data-feedback={feedback.messageKey} className="ml-6 flex flex-col gap-1 text-base leading-normal">
      <p>{why}</p>
      <p className="border-l-4 border-slate-400 pl-3">{how}</p>
    </div>
  );
}

function PhonemeRow({ phoneme }: { phoneme: PhonemeScore }) {
  const v = phoneme.verdict;
  return (
    <li data-verdict={v} className="flex flex-col gap-1">
      <span className="flex items-baseline gap-2">
        <span aria-hidden="true" className={`w-4 text-center ${TONE[v]}`}>
          {GLYPH[v]}
        </span>
        <span lang="en" className="font-mono">{`/${phoneme.expected}/`}</span>
        <span className={v === "wrong" ? "font-semibold text-rose-800" : "text-slate-700"}>
          {t(LABEL[v])}
        </span>
      </span>
      {phoneme.feedback && <Fix feedback={phoneme.feedback} />}
    </li>
  );
}

function WordDetail({ word }: { word: WordScore }) {
  return (
    <section id={DETAIL_ID} className="rounded-lg bg-white p-4 shadow">
      <h2 className="font-medium">{t("practice.detail", { word: word.text })}</h2>
      <ul className="mt-3 flex flex-col gap-3 text-lg">
        {word.phonemes.map((phoneme, i) => (
          <PhonemeRow key={i} phoneme={phoneme} />
        ))}
      </ul>
    </section>
  );
}

export function ScoreView({ result, selected, onSelect }: Props) {
  const word = selected === null ? undefined : result.words[selected];
  const needsWork = result.words.some((w) => w.verdict === "wrong");
  return (
    <>
      <p lang="en" className={CARD}>
        {pieces(result).map((piece, i) =>
          piece.kind === "gap" ? (
            <span key={i}>{piece.text}</span>
          ) : (
            <WordButton
              key={i}
              word={piece.word}
              selected={piece.index === selected}
              onClick={() => onSelect(piece.index === selected ? null : piece.index)}
            />
          ),
        )}
      </p>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-700">
        {ORDER.map((v) => (
          <li key={v} data-legend={v}>
            {t(LEGEND[v])}
          </li>
        ))}
      </ul>
      <p>{t(needsWork ? "practice.hint" : "practice.clean")}</p>
      {word && <WordDetail word={word} />}
    </>
  );
}
