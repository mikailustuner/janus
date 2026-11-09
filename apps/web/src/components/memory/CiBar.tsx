"use client";
/**
 * The confidence-interval bar (design.md shared rules, Req 16.6, 3.6, 29.5, P11): a log axis with
 * decade ticks, a mark at 1 ("no difference"), the range and the point estimate; the same numbers
 * as text in the caption. Neutral colours only (never `--risk`).
 */
import { useLocale } from "next-intl";

import { formatRatio } from "@/components/format";
import { ciBar, OVER, type Ratio } from "@/flow/memory";
import { useT } from "@/theme/words";

export function ratioText(x: number, locale: string, over: string): string {
  return x > OVER ? over : formatRatio(x, locale);
}

/** Decade ticks of the 0.1 … 1000 log axis, at 0, 25, 50, 75 and 100 %. */
const TICKS = [0.1, 1, 10, 100, 1000] as const;

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
  const nf = new Intl.NumberFormat(locale);
  return (
    <figure className="tile m-0 gap-2" data-testid="ci-bar">
      <figcaption className="mono text-sm text-fg">{text}</figcaption>
      <div className="relative mx-2 h-9" aria-hidden>
        <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-muted opacity-60" />
        {TICKS.map((x, i) => (
          <div
            key={x}
            className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-muted"
            style={{ left: `${i * 25}%` }}
          />
        ))}
        <div
          className="absolute top-0.5 bottom-0.5 w-0.5 -translate-x-1/2 rounded-full bg-fg"
          style={{ left: `${b.one}%` }}
        />
        <div
          className="absolute top-1/2 h-3 -translate-y-1/2 rounded-full bg-chip-fg opacity-70"
          style={{
            left: `${b.low}%`,
            width: `${Math.max(1, b.high - b.low)}%`,
          }}
        />
        <div
          className="absolute top-1/2 size-[18px] -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-accent bg-bg"
          style={{ left: `${b.ror}%` }}
        />
      </div>
      <div className="mono relative mx-2 h-4 text-xs text-muted" aria-hidden>
        {TICKS.map((x, i) => (
          <span
            key={x}
            className={`absolute top-0 whitespace-nowrap ${i === 0 ? "" : i === TICKS.length - 1 ? "-translate-x-full" : "-translate-x-1/2"}`}
            style={{ left: `${i * 25}%` }}
          >
            {nf.format(x)}
          </span>
        ))}
      </div>
      <p className="text-xs text-muted" aria-hidden>
        {t("MemoryView.noDifference")}
      </p>
    </figure>
  );
}
