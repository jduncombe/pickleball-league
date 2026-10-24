// Terminology table: the domain words the UI uses ("league", "team", "court"…),
// so a white-label brand can rename them (e.g. "ladder", "pair", "fixture").
//
// Defaults are in ./default-terms.json (shared with the API, which uses the
// same keys; see api/app/terms.py). A brand overrides any of them in
// web/brands/<brand>/terms.json; each entry may set `one`, `other` and
// `article` ("a" / "an" / ""). See docs/white-labelling.md.

import brandTerms from "@brand/terms.json";
import defaults from "./default-terms.json";

export type TermKey = keyof typeof defaults;

interface TermForms {
  one: string;
  other: string;
  article: string;
}

type Overrides = Partial<Record<TermKey, Partial<TermForms>>>;

const TERMS: Record<TermKey, TermForms> = Object.fromEntries(
  (Object.keys(defaults) as TermKey[]).map((key) => {
    const base = defaults[key];
    const override = (brandTerms as Overrides)[key] ?? {};
    const one = override.one ?? base.one;
    // A brand that only renames the singular gets a simple plural.
    const other = override.other ?? (override.one ? `${override.one}s` : base.other);
    return [key, { one, other, article: override.article ?? base.article }];
  }),
) as Record<TermKey, TermForms>;

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "team", or "teams" when `n` isn't 1. */
export function term(key: TermKey, n = 1): string {
  return n === 1 ? TERMS[key].one : TERMS[key].other;
}

/** Capitalised: "Team" / "Teams". */
export function Term(key: TermKey, n = 1): string {
  return capitalise(term(key, n));
}

/** "3 teams", "1 team". */
export function count(n: number, key: TermKey): string {
  return `${n} ${term(key, n)}`;
}

/** With its indefinite article: "a league", "an event". */
export function a(key: TermKey): string {
  const { article, one } = TERMS[key];
  return article ? `${article} ${one}` : one;
}

/** Capitalised `a()`: "A league". */
export function A(key: TermKey): string {
  return capitalise(a(key));
}
