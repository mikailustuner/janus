"use client";
/**
 * The confidence-interval bar (design.md shared rules, Req 16.6, 3.6, P11): a log axis, a mark at
 * 1 ("no difference"), the range and the point estimate; the same numbers as text next to it.
 * Neutral colours only (never `--risk`).
 */
import { useLocale } from "next-intl";

import { formatRatio } from "@/components/format";
import { ciBar, OVER, type Ratio } from "@/flow/memory";
import { useT } from "@/theme/words";

export function ratioText(x: number, locale: string, over: string): string {
  return x > OVER ? over : formatRatio(x, locale);
}

export function CiBar({ ratio }: { ratio: Ratio }) {
  const t = useT();
  const locale = useLocale();
  const b = ciBar(ratio);
  const over = t("MemoryView.over1000");
  const text = t("MemoryView.ratio", {
    ror: ratioText(ratio.ror, locale, over),
    low: ratioText(ratio.low, locale, over),
    high: ratioText(ratio.high, locale, over),
  });
  return (
    <figure className="flex flex-col gap-1" data-testid="ci-bar">
      <figcaption className="mono text-sm">{text}</figcaption>
      <div className="relative h-8" aria-hidden>
        <div className="absolute inset-x-0 top-[15px] h-0.5 rounded bg-muted" />
        <div
          className="absolute top-1.5 h-5 w-0.5 bg-fg"
          style={{ left: `${b.one}%` }}
        />
        <div
          className="absolute top-2.5 h-3 rounded-full bg-chip-fg opacity-60"
          style={{
            left: `${b.low}%`,
            width: `${Math.max(1, b.high - b.low)}%`,
          }}
        />
        <div
          className="absolute top-1.5 size-5 -translate-x-1/2 rounded-full border-[3px] border-accent bg-surface"
          style={{ left: `${b.ror}%` }}
        />
      </div>
      <p className="mono flex justify-between text-xs text-muted" aria-hidden>
        <span>0.1</span>
        <span>{t("MemoryView.noDifference")}</span>
        <span>1000</span>
      </p>
    </figure>
  );
}
