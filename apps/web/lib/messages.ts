// All learner-facing text comes from messages/vi.json; nothing is written inline (CLAUDE.md).
import vi from "../messages/vi.json";

type Params = Record<string, string | number>;

function lookup(key: string): string | undefined {
  const found = key
    .split(".")
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], vi);
  return typeof found === "string" ? found : undefined;
}

/** The text of `key`, with `{name}` placeholders filled from `params`. Throws on an unknown key. */
export function t(key: string, params: Params = {}): string {
  const text = lookup(key);
  if (text === undefined) throw new Error(`missing message: ${key}`);
  return text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}

/** The text for a key an API returned, or the generic error when this app has no copy for it. */
export function messageFor(key: string): string {
  return lookup(key) === undefined ? t("errors.internal") : t(key);
}
