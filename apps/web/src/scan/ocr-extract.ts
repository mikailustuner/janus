/**
 * Local extraction from recognised label text (experience design §6.4, DP10, Req 11.2, P22).
 * NDC shapes are offered as chips; any other text is only offered as tappable words. Nothing is
 * sent without the user's choice; a chosen selection is sent as exactly those words.
 */
const NDC = /\b(\d{4,5}-\d{3,4}-\d{1,2})\b/g;
const NDC_LABELLED = /\bNDC[:#\s]*(\d{10,11})\b/gi;

export function ndcCandidates(text: string): string[] {
  const out = new Set<string>();
  for (const m of text.matchAll(NDC)) out.add(m[1]!);
  for (const m of text.matchAll(NDC_LABELLED)) out.add(m[1]!);
  return [...out];
}

/** The query of a selection of adjacent words (2–100 characters, trimmed), else null. */
export function selectionQuery(
  words: readonly string[],
  selected: readonly number[],
): string | null {
  if (selected.length === 0) return null;
  const sorted = [...new Set(selected)].sort((a, b) => a - b);
  for (let i = 1; i < sorted.length; i++)
    if (sorted[i]! !== sorted[i - 1]! + 1) return null;
  const q = sorted
    .map((i) => words[i] ?? "")
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  return q.length >= 2 && q.length <= 100 ? q : null;
}
