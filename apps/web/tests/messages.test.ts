import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import vi from "../messages/vi.json";
import { messageFor, t } from "../lib/messages";

const ROOT = join(import.meta.dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(join(ROOT, dir), { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

const SOURCES = [...sourceFiles("app"), ...sourceFiles("lib")].map((path) => ({
  path,
  text: readFileSync(join(ROOT, path), "utf8"),
}));

function has(key: string): boolean {
  let node: unknown = vi;
  for (const part of key.split(".")) node = (node as Record<string, unknown> | undefined)?.[part];
  return typeof node === "string";
}

describe("learner-facing copy", () => {
  it("has no Vietnamese letter in the source: it all comes from messages/vi.json", () => {
    const vietnamese = /[À-ɏḀ-ỿ]/;
    const offenders = SOURCES.filter((file) => vietnamese.test(file.text)).map((file) => file.path);
    expect(offenders).toEqual([]);
  });

  it("has an entry in vi.json for every key the source names", () => {
    const keys = new Set<string>();
    for (const { text } of SOURCES) {
      for (const match of text.matchAll(/\b(?:t|messageFor)\(\s*"([\w.]+)"/g)) keys.add(match[1]);
      for (const match of text.matchAll(/"((?:errors|app|practice)\.[\w.]+)"/g)) keys.add(match[1]);
    }
    expect(keys.size).toBeGreaterThan(8);
    expect([...keys].filter((key) => !has(key))).toEqual([]);
  });

  it("has an entry for every microphone problem the recorder can raise", () => {
    const recorder = SOURCES.find((file) => file.path.endsWith("recorder.ts"))!.text;
    const union = /export type MicProblem =([^;]+);/.exec(recorder)![1];
    const problems = [...union.matchAll(/"(\w+)"/g)].map((match) => match[1]);
    expect(problems.length).toBe(4);
    expect(problems.filter((problem) => !has(`errors.mic.${problem}`))).toEqual([]);
  });

  it("has the keys that the services return for the errors this flow can meet", () => {
    for (const key of [
      "errors.speech.busy",
      "errors.audio.undecodable",
      "errors.audio.too_large",
      "errors.audio.too_long",
      "errors.audio.too_short",
      "errors.not_ready",
      "errors.validation",
      "errors.internal",
      "errors.http",
    ]) {
      expect(has(key), key).toBe(true);
    }
  });
});

describe("t and messageFor", () => {
  it("fills {name} placeholders and leaves an unknown one visible", () => {
    expect(t("pronunciation.fix.generic.why", { expected: "θ", word: "think" })).toContain("θ");
    expect(t("pronunciation.fix.generic.why", { expected: "θ" })).toContain("{word}");
  });

  it("throws on a key with no copy, so a typo cannot reach a learner as a blank", () => {
    expect(() => t("practice.nope")).toThrow("missing message");
  });

  it("falls back to the generic error for a key an API returns that this app has no copy for", () => {
    expect(messageFor("errors.something.new")).toBe(t("errors.internal"));
    expect(messageFor("errors.speech.busy")).toBe(t("errors.speech.busy"));
  });
});
