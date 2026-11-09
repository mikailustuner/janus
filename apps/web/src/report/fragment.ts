/**
 * Prefill fragments of the assistant (report-assistant design §3.4, Req 2.4, 2.5, 8.1, DP10, P8).
 * Codes and item positions only; never a box name, a date or free text. Pure, never throws.
 */
export type Prefill =
  | {
      src: "finding";
      ingredient: string;
      event: string | null;
      items: number[];
    }
  | { src: "list" }
  | {
      src: "doctor";
      rule: string;
      ingredient: string;
      others: string[];
      demo: boolean;
    };

const KEY = /^(?:Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$/;
const EVENT = /^[a-z][a-z0-9_]{0,39}$/;
const RULE = /^pipc:[1-9][0-9]{0,3}$/;
const MAX_ITEMS = 500;
const MAX_OTHERS = 50;

const keys = (s: string | null) =>
  [...new Set((s ?? "").split(",").filter((k) => KEY.test(k)))].slice(
    0,
    MAX_OTHERS,
  );

export function parsePrefill(hash: string): Prefill | null {
  try {
    const p = new URLSearchParams(hash.startsWith("#") ? hash.slice(1) : hash);
    const src = p.get("src");
    if (src === "list") return { src: "list" };
    const ing = p.get("ing") ?? "";
    if (!KEY.test(ing)) return null;
    if (src === "finding") {
      const event = p.get("event");
      const items = [
        ...new Set(
          (p.get("items") ?? "")
            .split(",")
            .filter((x) => /^[0-9]{1,3}$/.test(x))
            .map(Number)
            .filter((n) => n < MAX_ITEMS),
        ),
      ];
      return {
        src,
        ingredient: ing,
        event: event && EVENT.test(event) ? event : null,
        items,
      };
    }
    if (src === "doctor") {
      const rule = p.get("rule") ?? "";
      if (!RULE.test(rule)) return null;
      return {
        src,
        rule,
        ingredient: ing,
        others: keys(p.get("with")).filter((k) => k !== ing),
        demo: p.get("demo") === "1",
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function buildPrefill(p: Prefill): string {
  const q = new URLSearchParams({ src: p.src });
  if (p.src === "finding") {
    q.set("ing", p.ingredient);
    if (p.event) q.set("event", p.event);
    if (p.items.length) q.set("items", p.items.join(","));
  } else if (p.src === "doctor") {
    q.set("rule", p.rule);
    q.set("ing", p.ingredient);
    if (p.others.length) q.set("with", p.others.join(","));
    if (p.demo) q.set("demo", "1");
  }
  return q.toString();
}
