/**
 * Ingredient names in recognised label text (ocr-first design §3, Req 3, P1–P6). Pure, on the
 * device: the text is compared with the accepted ingredient names of the five languages
 * (`vocabulary/ingredient-names.json`). The result is a list of candidates for the user to
 * choose from; nothing here selects one.
 *
 * Three strengths, strongest first:
 *  - `exact`    the words equal a held name after case and diacritic folding;
 *  - `variant`  they equal one after the spelling rules that separate the same name between
 *               languages (amlodipine / amlodipin / amlodipina, ph / f, x / ks, c / k, …);
 *  - `close`    one word is within a small edit distance of a held name (a misread letter).
 *               The distance is capped by the length of the name and is never more than 2.
 * Salt words (hydrochloride, besilat, sodique, …) never make a candidate next to another
 * ingredient; they are kept in `written`, the text as printed.
 */

export type Strength = "exact" | "variant" | "close";

export interface IngredientCandidate {
  /** Ingredient key of the vocabulary (a Wikidata QID or a Janus key). */
  key: string;
  strength: Strength;
  /** Edit distance to the held name; 0 unless `close`. */
  distance: number;
  /** The words as printed on the label, with their salt words. */
  written: string;
}

export interface NameIndex {
  exact: Map<string, string[]>;
  variant: Map<string, string[]>;
  /** Single-word names by skeleton, for the tolerant comparison. */
  singles: { skeleton: string; keys: string[] }[];
}

/** Case and diacritic folding: lower case, marks removed, ı ß æ œ ø ł đ spelled out. */
export function fold(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/ı/g, "i")
    .replace(/ß/g, "ss")
    .replace(/æ/g, "ae")
    .replace(/œ/g, "oe")
    .replace(/ø/g, "o")
    .replace(/ł/g, "l")
    .replace(/đ/g, "d");
}

/**
 * The spelling skeleton of one folded word: the same INN written in English, Turkish, German,
 * French, Spanish, Italian, Portuguese, Dutch, Polish or Latin gives the same skeleton in most
 * cases. Two different ingredients may share one; then both are offered.
 */
export function skeleton(word: string): string {
  let w = word
    .replace(/ph/g, "f")
    .replace(/th/g, "t")
    .replace(/ch/g, "c")
    .replace(/y/g, "i")
    .replace(/w/g, "v")
    .replace(/c(?=[ei])/g, "s")
    .replace(/qu/g, "k")
    .replace(/k/g, "c")
    .replace(/x/g, "cs")
    .replace(/z/g, "s")
    .replace(/g(?=[ei])/g, "j")
    .replace(/^es(?=[ptc])/, "s")
    .replace(/(.)\1+/g, "$1");
  if (w.length >= 7) w = w.replace(/(um|us)$/, "");
  if (w.length >= 6) w = w.replace(/[aeo]$/, "");
  return w;
}

/** The folded words of a held name; a word in another script (γ) is left out, as in a label. */
const words = (text: string) =>
  (text.match(/[\p{L}\p{N}]+/gu) ?? []).filter((w) => /^[a-z0-9]+$/.test(w));

/** The longest tolerated edit distance for a name skeleton of this length. */
export function distanceCap(length: number): 0 | 1 | 2 {
  return length < 6 ? 0 : length < 9 ? 1 : 2;
}

/** Optimal string alignment distance (insert, delete, replace, swap), or `cap + 1` if larger. */
export function editDistance(a: string, b: string, cap: number): number {
  if (Math.abs(a.length - b.length) > cap) return cap + 1;
  let prev2: number[] = [];
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let d = Math.min(prev[j]! + 1, row[j - 1]! + 1, prev[j - 1]! + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1])
        d = Math.min(d, prev2[j - 2]! + 1);
      row.push(d);
      if (d < best) best = d;
    }
    if (best > cap) return cap + 1;
    prev2 = prev;
    prev = row;
  }
  return Math.min(prev[b.length]!, cap + 1);
}

/** Salt, ester and hydrate words in the five languages (and Latin), as printed on labels. */
const SALT_WORDS =
  `hydrochloride dihydrochloride hcl chlorhydrate dichlorhydrate clorhidrato
hidrocloruro dihidrocloruro diclorhidrato hidroklorur dihidroklorur hydrochlorid dihydrochlorid
cloridrato hydrochloridum besilate besylate besilat besilato mesilate mesylate mesilat mesilato
maleate maleat maleato hydrogenmaleat succinate succinat succinato suksinat tartrate tartrat
tartrato tartarat bitartrate hydrogentartrat fumarate fumarat fumarato hemifumarate hemifumarat
citrate citrat citrato sitrat sulfate sulphate sulfat sulfato hydrogensulfat phosphate phosphat
fosfat fosfato acetate acetat acetato asetat sodium natrium sodique sodico sodica sodyum disodium
potassium kalium potassique potasico potasica potasyum calcium calcique calcico calcica kalsiyum
magnesium magnesique magnesico magnesica magnezyum bromide hydrobromide bromhydrate bromhidrato
hidrobromur hydrobromid nitrate nitrat nitrato monohydrate dihydrate trihydrate hemihydrate
sesquihydrate anhydrous monohydrat dihydrat trihydrat hemihydrat monohidrat dihidrat trihidrat
monohidrato dihidrato trihidrato anhydre anhidro susuz arginine arginin arginina erbumine
erbumin propionate dipropionate valerate furoate olamine tromethamine trometamol pamoate
embonate oxalate oxalat oxalato oksalat medoxomil cilexetil sileksetil axetil carbonate carbonat
karbonat carbonato chloride chlorid chlorure cloruro klorur`.split(/\s+/);

/** Words that join a salt to its ingredient ("chlorhydrate de metformine"). */
const CONNECTORS = new Set(["de", "d", "di", "of", "als", "as", "como"]);

/**
 * Frequent label words within the tolerated distance of an ingredient name. They are never
 * compared tolerantly (an exact name still matches).
 */
const STOP_WORDS =
  `tablet tablets tablette tabletten tabletler comprime comprimes comprimido
comprimidos capsule capsules kapsel kapseln kapsul gelule gelules capsula capsulas contains
contient contiene enthalt icerir children kinder enfants ninos cocuklarin`.split(
    /\s+/,
  );

const SALTS = new Set(SALT_WORDS.map(skeleton));
const STOPS = new Set(STOP_WORDS.map(skeleton));
const SALT_SUFFIXES = [...SALTS].filter((s) => s.length >= 5);

const add = (map: Map<string, string[]>, k: string, key: string) => {
  const list = map.get(k);
  if (!list) map.set(k, [key]);
  else if (!list.includes(key)) list.push(key);
};

/** Builds the lookup from `key → names in any language` (the English name first). */
export function buildIndex(
  names: Readonly<Record<string, readonly string[]>>,
): NameIndex {
  const exact = new Map<string, string[]>();
  const variant = new Map<string, string[]>();
  const singles = new Map<string, string[]>();
  // Two keys with the same first (English) name are one ingredient here: the user sees one
  // name and the request is that name.
  const first = new Map<string, string>();
  for (const [k, list] of Object.entries(names)) {
    const en = fold(list[0] ?? "");
    if (!first.has(en)) first.set(en, k);
  }
  for (const [k, list] of Object.entries(names))
    for (const name of list) {
      const key = first.get(fold(list[0] ?? "")) ?? k;
      const w = words(fold(name));
      if (w.length === 0) continue;
      add(exact, w.join(" "), key);
      add(variant, w.map(skeleton).join(" "), key);
      if (w.length === 1) add(singles, skeleton(w[0]!), key);
    }
  return {
    exact,
    variant,
    singles: [...singles].map(([s, keys]) => ({ skeleton: s, keys })),
  };
}

interface Token {
  text: string;
  folded: string;
  skeleton: string;
  start: number;
  end: number;
  /** A digit was read as its look-alike letter (0 → o, 1 → l, 5 → s). */
  repaired: boolean;
}

function tokens(line: string): Token[] {
  const out: Token[] = [];
  for (const m of line.matchAll(/[\p{L}\p{N}]+/gu)) {
    let folded = fold(m[0]);
    // A folded letter may be more than one word character apart (never for the letters above).
    if (!/^[a-z0-9]+$/.test(folded)) continue;
    let repaired = false;
    if (/[a-z]{3}/.test(folded) && /[015]/.test(folded)) {
      folded = folded.replace(/0/g, "o").replace(/1/g, "l").replace(/5/g, "s");
      repaired = true;
    }
    out.push({
      text: m[0],
      folded,
      skeleton: skeleton(folded),
      start: m.index,
      end: m.index + m[0].length,
      repaired,
    });
  }
  return out;
}

const RANK: Record<Strength, number> = { exact: 0, variant: 1, close: 2 };
const MAX_WORDS = 4;
/** More keys than this at the same distance is not a candidate list but a guess. */
const MAX_TIED = 3;

/** The printed words of tokens `i..j` with the salt words around them, from one line. */
function written(line: string, t: Token[], i: number, j: number): string {
  let a = i;
  let b = j;
  for (let n = 0; n < 2 && b + 1 < t.length; n++)
    if (SALTS.has(t[b + 1]!.skeleton)) b++;
    else break;
  for (let n = 0; n < 2 && a > 0; n++) {
    if (SALTS.has(t[a - 1]!.skeleton)) a--;
    else if (
      a > 1 &&
      CONNECTORS.has(t[a - 1]!.folded) &&
      SALTS.has(t[a - 2]!.skeleton)
    )
      a -= 2;
    else break;
  }
  return line.slice(t[a]!.start, t[b]!.end);
}

/** A compound of a name and a salt written as one word ("Metoprololsuccinat"). */
function compoundStem(s: string): string | null {
  for (const salt of SALT_SUFFIXES)
    if (s.endsWith(salt) && s.length - salt.length >= 5)
      return s.slice(0, -salt.length);
  return null;
}

/**
 * The ingredient candidates of the recognised lines, strongest first, one per ingredient. An
 * empty list means nothing was close enough; the caller then offers the words and typing.
 */
export function matchIngredients(
  lines: readonly string[],
  index: NameIndex,
): IngredientCandidate[] {
  const found: (IngredientCandidate & { order: number })[] = [];
  const saltOnly: typeof found = [];
  let order = 0;
  const push = (
    into: typeof found,
    keys: readonly string[],
    strength: Strength,
    distance: number,
    text: string,
  ) => {
    for (const key of keys)
      into.push({ key, strength, distance, written: text, order: order++ });
  };

  for (const line of lines) {
    const t = tokens(line);
    for (let i = 0; i < t.length;) {
      let used = 0;
      for (let n = Math.min(MAX_WORDS, t.length - i); n >= 1 && !used; n--) {
        const span = t.slice(i, i + n);
        const salt = n === 1 && SALTS.has(span[0]!.skeleton);
        const repaired = span.some((x) => x.repaired);
        const text = written(line, t, i, i + n - 1);
        const exact = index.exact.get(span.map((x) => x.folded).join(" "));
        const variant =
          exact ?? index.variant.get(span.map((x) => x.skeleton).join(" "));
        if (!variant) continue;
        push(
          salt ? saltOnly : found,
          variant,
          repaired ? "close" : exact ? "exact" : "variant",
          repaired ? 1 : 0,
          text,
        );
        used = n;
      }
      if (used) {
        i += used;
        continue;
      }
      const tok = t[i]!;
      i++;
      if (SALTS.has(tok.skeleton) || STOPS.has(tok.skeleton)) continue;
      const text = written(line, t, i - 1, i - 1);
      const stem = compoundStem(tok.skeleton);
      const compound =
        stem && (index.variant.get(stem) ?? index.variant.get(skeleton(stem)));
      if (compound) {
        push(found, compound, tok.repaired ? "close" : "variant", 0, text);
        continue;
      }
      // A name the recogniser split in two ("Met formina"): the two words together. Only for
      // parts of three letters or more and a name of eight or more, so that scraps of a badly
      // read photo do not add up to a short name.
      const next = t[i];
      const joinedSkeleton =
        next && tok.folded.length >= 3 && next.folded.length >= 3
          ? skeleton(tok.folded + next.folded)
          : "";
      const joined =
        joinedSkeleton.length >= 8
          ? index.variant.get(joinedSkeleton)
          : undefined;
      if (joined) {
        push(found, joined, "close", 1, written(line, t, i - 1, i));
        i++;
        continue;
      }
      // Tolerant comparison of one word, and of the stem of a compound.
      let best = 3;
      let keys: string[] = [];
      for (const s of stem ? [tok.skeleton, stem] : [tok.skeleton])
        for (const name of index.singles) {
          const cap = distanceCap(name.skeleton.length);
          if (cap === 0) continue;
          const d = editDistance(s, name.skeleton, Math.min(cap, best));
          if (d > cap || d > best) continue;
          if (d < best) {
            best = d;
            keys = [];
          }
          for (const k of name.keys) if (!keys.includes(k)) keys.push(k);
        }
      if (keys.length > 0 && keys.length <= MAX_TIED)
        push(found, keys, "close", best, text);
    }
  }

  const list = found.length > 0 ? found : saltOnly;
  list.sort(
    (a, b) =>
      RANK[a.strength] - RANK[b.strength] ||
      a.distance - b.distance ||
      a.order - b.order,
  );
  const seen = new Set<string>();
  const out: IngredientCandidate[] = [];
  for (const { key, strength, distance, written: text } of list) {
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ key, strength, distance, written: text });
  }
  return out;
}
