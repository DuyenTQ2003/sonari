import { readFileSync } from "node:fs";
import { join } from "node:path";
import Ajv2020 from "ajv/dist/2020";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GLYPH, ScoreView, SHAPE } from "../app/result";
import { t } from "../lib/messages";
import { isDebug, pieces, step, type ScoreResponse, type Verdict } from "../lib/score";
import {
  ALL_CORRECT,
  ALL_UNCLEAR,
  FIXTURES,
  MIXED,
  WRONG_WITH_FEEDBACK,
  response,
} from "./fixtures";

const SCHEMA = JSON.parse(
  readFileSync(
    join(import.meta.dirname, "../../../packages/contracts/schema/score-response.schema.json"),
    "utf8",
  ),
);
const validate = new Ajv2020({ allowUnionTypes: true }).compile(SCHEMA);
const VERDICTS: Verdict[] = ["correct", "unclear", "wrong"];

function render(result: ScoreResponse, selected: number | null = null): string {
  return renderToStaticMarkup(<ScoreView result={result} selected={selected} onSelect={() => {}} />);
}

function text(html: string): string {
  return html
    .replace(/<[^>]+>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, "&");
}

const attrs = (html: string, name: string): string[] =>
  [...html.matchAll(new RegExp(`${name}="([^"]*)"`, "g"))].map((match) => match[1]);

const wordVerdicts = (html: string): string[] =>
  [...html.matchAll(/<button[^>]*data-verdict="(\w+)"/g)].map((match) => match[1]);

const rowVerdicts = (html: string): string[] =>
  [...html.matchAll(/<li data-verdict="(\w+)"/g)].map((match) => match[1]);

/** The sentence the learner reads: the first paragraph, without the screen-reader labels. */
function sentence(html: string): string {
  const paragraph = /<p [^>]*>(.*?)<\/p>/.exec(html)![1];
  return text(paragraph.replace(/<span lang="vi" class="sr-only">.*?<\/span>/g, ""));
}

describe("the fixtures are what the service can answer", () => {
  it.each(Object.entries(FIXTURES))("%s validates against the contract's JSON Schema", (_, fixture) => {
    expect(validate(fixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it("is checked by a validator that can say no", () => {
    const { words: _, ...noWords } = MIXED;
    expect(validate(noWords)).toBe(false);
    const odd = structuredClone(WRONG_WITH_FEEDBACK);
    odd.words[1].phonemes[0].feedback!.messageKey = "Pronunciation.Fix";
    expect(validate(odd)).toBe(false);
  });

  it.each(Object.entries(FIXTURES))("%s keeps the contract's promises the schema cannot state", (_, fixture) => {
    for (const word of fixture.words) {
      const worst = VERDICTS.toReversed().find((v) => word.phonemes.some((p) => p.verdict === v));
      expect(word.verdict).toBe(worst);
      expect(word.correctPhonemes).toBe(word.phonemes.filter((p) => p.verdict === "correct").length);
      for (const p of word.phonemes) {
        expect(p.feedback !== null).toBe(p.verdict === "wrong");
        expect(p.heard === null).toBe(p.verdict === "correct");
      }
    }
  });
});

describe("a recording with every phoneme correct", () => {
  const html = render(ALL_CORRECT);

  it("shows the sentence as it was written, every word marked correct", () => {
    expect(sentence(html)).toBe("One think you.");
    expect(wordVerdicts(html)).toEqual(["correct", "correct", "correct"]);
  });

  it("says nothing needs fixing, and shows no detail until a word is picked", () => {
    expect(text(html)).toContain(t("practice.clean"));
    expect(html).not.toContain('data-verdict="wrong"');
    expect(html).not.toContain("<section");
  });
});

describe("a recording with all three verdicts", () => {
  const html = render(MIXED);

  it("marks each word by its worst phoneme, in sentence order", () => {
    expect(sentence(html)).toBe("Thank you very much.");
    expect(wordVerdicts(html)).toEqual(["wrong", "correct", "unclear", "wrong"]);
    expect(text(html)).toContain(t("practice.hint"));
  });

  it("lists the phonemes of the picked word, and the why and how of each wrong one", () => {
    const picked = render(MIXED, 0); // Thank: θ wrong, æ correct, ŋ unclear, k correct
    expect(rowVerdicts(picked)).toEqual(["wrong", "correct", "unclear", "correct"]);
    expect(attrs(picked, "data-feedback")).toEqual(["pronunciation.fix.th_stop"]);
    const params = { word: "Thank", expected: "θ", heard: "t" };
    expect(text(picked)).toContain(t("pronunciation.fix.th_stop.why", params));
    expect(text(picked)).toContain(t("pronunciation.fix.th_stop.how", params));
    expect(text(picked)).toContain(t("practice.detail", { word: "Thank" }));
  });

  it("gives another wrong word its own rule", () => {
    expect(attrs(render(MIXED, 3), "data-feedback")).toEqual(["pronunciation.fix.final_consonant"]);
  });

  it("shows an unclear phoneme as unclear: no error, no fix", () => {
    const picked = render(MIXED, 2); // very: v unclear, the rest correct
    expect(rowVerdicts(picked)).toEqual(["unclear", "correct", "correct", "correct"]);
    const detail = picked.slice(picked.indexOf("<section")); // the sentence still has wrong words
    expect(detail).not.toContain("data-feedback");
    expect(detail).not.toContain('data-verdict="wrong"');
    expect(text(detail)).toContain(t("practice.verdict.unclear"));
  });

  it("marks the picked word as pressed and no other", () => {
    expect(attrs(render(MIXED, 1), "aria-pressed")).toEqual(["false", "true", "false", "false"]);
    expect(attrs(html, "aria-pressed")).toEqual(["false", "false", "false", "false"]);
  });

  it("tells correct, unclear and wrong apart without colour", () => {
    // The underline styles and the glyphs are three different things, whatever the colours.
    expect(new Set(Object.values(SHAPE)).size).toBe(3);
    expect(new Set(Object.values(GLYPH)).size).toBe(3);
    const colour = /^(text|bg|ring|decoration)-(slate|rose|emerald)-\d+$/;
    const shapes = new Map<string, string>();
    for (const match of html.matchAll(/<button[^>]*data-verdict="(\w+)"[^>]*class="([^"]*)"/g)) {
      const shape = match[2].split(" ").filter((c) => !colour.test(c)).sort().join(" ");
      expect(shapes.get(match[1]) ?? shape).toBe(shape); // the same verdict, the same shape
      shapes.set(match[1], shape);
    }
    expect(new Set(shapes.values()).size).toBe(3);
    // Words say it to a screen reader, phoneme rows say it in words, the legend explains it.
    const labels = VERDICTS.map((v) => t(`practice.verdict.${v}`));
    expect(new Set(labels).size).toBe(3);
    const rows = text(render(MIXED, 0)); // θ wrong, æ correct, ŋ unclear, k correct
    for (const label of labels) {
      expect(html).toContain(` (${label})`);
      expect(rows).toContain(label);
    }
    expect(attrs(html, "data-legend")).toEqual(["wrong", "unclear", "correct"]);
    expect(new Set(VERDICTS.map((v) => t(`practice.legend.${v}`))).size).toBe(3);
  });

  it("shows no percentage, score or number, whichever word is picked", () => {
    for (const fixture of Object.values(FIXTURES)) {
      for (let i = -1; i < fixture.words.length; i++) {
        expect(text(render(fixture, i < 0 ? null : i))).not.toMatch(/\d|%/);
      }
    }
  });
});

describe("a recording the model is unsure about", () => {
  const html = render(ALL_UNCLEAR);

  it("marks every word unclear and nothing as an error", () => {
    expect(wordVerdicts(html)).toEqual(["unclear", "unclear"]);
    expect(html).not.toContain('data-verdict="wrong"');
    expect(html).not.toContain(SHAPE.wrong);
    expect(html).not.toContain('role="alert"');
    expect(text(html)).toContain(t("practice.clean"));
  });

  it("explains no fix for any of its phonemes", () => {
    for (let i = 0; i < ALL_UNCLEAR.words.length; i++) {
      const picked = render(ALL_UNCLEAR, i);
      expect(new Set(rowVerdicts(picked))).toEqual(new Set(["unclear"]));
      expect(picked).not.toContain("data-feedback");
    }
  });
});

describe("a wrong phoneme with feedback", () => {
  it("shows the generic explanation for the substituted /t/", () => {
    const html = render(WRONG_WITH_FEEDBACK, 1);
    expect(wordVerdicts(html)).toEqual(["correct", "wrong", "correct"]);
    expect(rowVerdicts(html)).toEqual(["wrong", "correct", "correct", "correct"]);
    const params = { word: "tink", expected: "t", heard: "θ" };
    expect(text(html)).toContain(t("pronunciation.fix.generic.why", params));
    expect(text(html)).toContain(t("pronunciation.fix.generic.how", params));
  });

  it("falls back to the generic explanation for a rule this app has no copy for", () => {
    const future = structuredClone(WRONG_WITH_FEEDBACK);
    future.words[1].phonemes[0].feedback!.messageKey = "pronunciation.fix.not_written_yet";
    const html = render(future, 1);
    const params = { word: "tink", expected: "t", heard: "θ" };
    expect(text(html)).toContain(t("pronunciation.fix.generic.why", params));
    expect(text(html)).not.toContain("not_written_yet");
  });

  it("keeps a wrong word wrong whatever else it holds", () => {
    const [word] = response("Tink", [["Tink", [["t", "wrong", "θ"], ["ɪ", "unclear", "i"], ["k", "correct"]]]]).words;
    expect(word.verdict).toBe("wrong");
  });
});

describe("the sentence is cut where the service says the words are", () => {
  it("keeps the punctuation and spaces between words as plain text", () => {
    const parts = pieces(MIXED).map((p) => (p.kind === "gap" ? p.text : `[${p.word.text}]`));
    expect(parts).toEqual(["[Thank]", " ", "[you]", " ", "[very]", " ", "[much]", "."]);
  });

  it("counts code points like the service, not UTF-16 units", () => {
    const wow = response("Wow \u{1F600} you.", [
      ["Wow", [["w", "correct"]]],
      ["you", [["j", "correct"]]],
    ]);
    expect(wow.words.map((w) => [w.start, w.end])).toEqual([[0, 3], [6, 9]]);
    expect(pieces(wow).map((p) => (p.kind === "gap" ? p.text : p.word.text))).toEqual([
      "Wow",
      " \u{1F600} ",
      "you",
      ".",
    ]);
  });
});

describe("the sentence picker and the debug view", () => {
  it("steps forward and back around the list", () => {
    expect([step(0, 1, 3), step(2, 1, 3), step(0, -1, 3), step(1, -1, 3)]).toEqual([1, 0, 2, 0]);
    expect(step(0, 1, 1)).toBe(0);
  });

  it("shows the raw response only behind ?debug", () => {
    expect(isDebug("?debug")).toBe(true);
    expect(isDebug("?debug=1&x=2")).toBe(true);
    expect(isDebug("")).toBe(false);
    expect(isDebug("?x=debug")).toBe(false);
  });
});
