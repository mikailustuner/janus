/**
 * Card primitives (experience Req 29, design §21, DP50–DP53; steering design.md "Cards and layout
 * system"): a large title, inset grouped lists, summary cards, stat tiles, a disclosure and a
 * segmented control. Tokens only; the theme changes values (radii, surface, blur), not markup.
 */
import type { ComponentProps, ReactNode } from "react";

import { ChevronIcon } from "@/components/icons";
import { Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useT } from "@/theme/words";

/** The page's one `h1`, with an optional eyebrow above and a one-line summary under it. */
export function LargeTitle({
  title,
  eyebrow,
  summary,
  summaryTestId,
}: {
  title: ReactNode;
  eyebrow?: ReactNode;
  summary?: ReactNode;
  summaryTestId?: string;
}) {
  return (
    <header className="flex flex-col gap-1.5">
      {eyebrow ? (
        <p className="text-sm font-bold text-muted">{eyebrow}</p>
      ) : null}
      <h1 className="large-title">{title}</h1>
      {summary ? (
        <p className="text-lg text-muted" data-testid={summaryTestId}>
          {summary}
        </p>
      ) : null}
    </header>
  );
}

/**
 * An inset grouped list: a section header above, rows with hairlines inset from the leading edge,
 * a footer under it. `plain` is the same list inside a card (no second surface).
 */
export function GroupedList({
  header,
  headingId,
  level = 2,
  footer,
  plain = false,
  children,
  className = "",
  ...rest
}: {
  header?: ReactNode;
  headingId?: string;
  level?: 2 | 3;
  footer?: ReactNode;
  plain?: boolean;
  children: ReactNode;
  className?: string;
} & Omit<ComponentProps<"section">, "children" | "className">) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <section
      aria-labelledby={header && headingId ? headingId : undefined}
      className={`flex min-w-0 flex-col gap-2 ${className}`}
      {...rest}
    >
      {header ? (
        <H
          id={headingId}
          className={plain ? "font-body font-bold" : "group-header"}
        >
          {header}
        </H>
      ) : null}
      <ul className={plain ? "grouped-plain" : "grouped"}>{children}</ul>
      {footer ? (
        <div
          className={`flex flex-col gap-1 ${plain ? "text-sm text-muted" : "group-footer"}`}
        >
          {footer}
        </div>
      ) : null}
    </section>
  );
}

/** One row of a grouped list. */
export function Row({
  children,
  className = "",
  ...rest
}: { children: ReactNode; className?: string } & Omit<
  ComponentProps<"li">,
  "children" | "className"
>) {
  return (
    <li className={`flex min-w-0 flex-col gap-1 ${className}`} {...rest}>
      {children}
    </li>
  );
}

/** A row that navigates: the whole row is one link with a chevron. */
export function RowLink({
  href,
  children,
  onClick,
}: {
  href: ComponentProps<typeof Link>["href"];
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <li className="row-link">
      <Link href={href} onClick={onClick}>
        <span className="min-w-0 flex-1">{children}</span>
        <ChevronIcon size={18} className="shrink-0 text-muted" />
      </Link>
    </li>
  );
}

/** Back to the parent screen, named by it ("‹ Results"); screen readers hear "Back: Results". */
export function BackLink({
  href,
  children,
}: {
  href: ComponentProps<typeof Link>["href"];
  children: ReactNode;
}) {
  const t = useT();
  return (
    <Link
      href={href}
      className="-ms-2 inline-flex min-h-11 w-fit items-center gap-1 rounded-full pe-3 ps-1 font-bold text-accent no-underline transition-colors duration-150 hover:bg-chip"
    >
      <ChevronIcon size={22} className="shrink-0 rotate-180" />
      <span className="sr-only">{t("Common.back")}: </span>
      {children}
    </Link>
  );
}

/** A card with a title, an optional eyebrow and one summary line, then its body. */
export function SummaryCard({
  title,
  id,
  eyebrow,
  summary,
  leading,
  level = 2,
  as = "section",
  className = "",
  children,
  ...rest
}: {
  title: ReactNode;
  id?: string;
  eyebrow?: ReactNode;
  summary?: ReactNode;
  leading?: ReactNode;
  level?: 1 | 2 | 3;
  as?: "section" | "article" | "div" | "li" | "aside";
  className?: string;
  children?: ReactNode;
} & Omit<
  ComponentProps<"section">,
  "className" | "children" | "ref" | "title"
>) {
  const H = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
  return (
    <Card
      as={as}
      aria-labelledby={id}
      className={`gap-stack sm:p-5 ${className}`}
      {...rest}
    >
      <header className="flex items-start gap-3">
        {leading}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {eyebrow ? <p className="text-sm text-muted">{eyebrow}</p> : null}
          <H
            id={id}
            className={
              level === 1
                ? "large-title"
                : "font-body text-lg leading-snug font-bold"
            }
          >
            {title}
          </H>
          {summary ? <div className="text-muted">{summary}</div> : null}
        </div>
      </header>
      {children}
    </Card>
  );
}

/**
 * A big number (DP53): the figure and its label are for the eye, the sentence (with the same
 * number) is what screen readers and text checks read. Without a sentence the tile repeats a
 * sentence that is visible next to it, so it is hidden from assistive technology as a whole.
 */
export function StatTile({
  value,
  label,
  sentence,
  className = "",
}: {
  value: string;
  label: ReactNode;
  sentence?: string;
  className?: string;
}) {
  return (
    <div
      className={`tile ${className}`}
      aria-hidden={sentence ? undefined : true}
    >
      <span aria-hidden className="tile-value">
        {value}
      </span>
      <span aria-hidden className="tile-label">
        {label}
      </span>
      {sentence ? <span className="sr-only">{sentence}</span> : null}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-2">
      {children}
    </div>
  );
}

/** Folded detail on `<details>` (DP51): platform semantics, content in the document while closed. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  className = "",
  summaryClassName = "",
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  summaryClassName?: string;
}) {
  return (
    <details
      className={`disclosure ${className}`}
      open={defaultOpen || undefined}
    >
      <summary className={summaryClassName}>
        <span className="min-w-0">{summary}</span>
        <ChevronIcon size={18} className="disclosure-chevron" />
      </summary>
      <div className="disclosure-body flex flex-col gap-2 pt-1 pb-1">
        {children}
      </div>
    </details>
  );
}

export type SegmentOption<T extends string> = {
  value: T;
  label: ReactNode;
};

/** The checked option: the value when it is one of the options, otherwise the first option. */
export function checkedOption<T extends string>(
  options: readonly SegmentOption<T>[],
  value: T | null | undefined,
): T | undefined {
  return options.some((o) => o.value === value) ? value! : options[0]?.value;
}

/**
 * One choice among a few views or filters (DP52): a fieldset of native radios, each stretched
 * over its segment, so arrow keys, focus and "1 of 4" come from the platform.
 */
export function SegmentedControl<T extends string>({
  legend,
  legendVisible = false,
  name,
  options,
  value,
  onChange,
  variant = "segmented",
  className = "",
}: {
  legend: ReactNode;
  legendVisible?: boolean;
  name: string;
  options: readonly SegmentOption<T>[];
  value: T | null | undefined;
  onChange: (value: T) => void;
  variant?: "segmented" | "pills";
  className?: string;
}) {
  const current = checkedOption(options, value);
  return (
    <fieldset className={`m-0 min-w-0 border-0 p-0 ${className}`}>
      <legend className={legendVisible ? "mb-2 font-bold" : "sr-only"}>
        {legend}
      </legend>
      <div className={variant === "pills" ? "pills" : "segmented"}>
        {options.map((o) => (
          <label key={o.value} className="segment">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={current === o.value}
              onChange={() => onChange(o.value)}
            />
            <span className="min-w-0 [overflow-wrap:anywhere]">{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
