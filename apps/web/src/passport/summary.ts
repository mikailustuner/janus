/**
 * The one-line summary of a box's presence answer (experience Req 29.2, P31): in how many of the
 * checked sources a product with the same active ingredients is listed. A source that could not be
 * checked counts for neither number; with no checked source there is no summary.
 */
import type { ItemOut } from "./model";

export function presenceSummary(
  out: Pick<ItemOut, "answers">,
): { listed: number; checked: number } | null {
  const checked = out.answers.filter(
    (a) => a.status !== "source_unavailable",
  ).length;
  if (checked === 0) return null;
  const listed = out.answers.filter((a) => a.status === "present").length;
  return { listed, checked };
}
