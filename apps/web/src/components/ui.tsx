/**
 * Primitives built in-repo on the design tokens (DP26; owner decision 4: no shadcn/ui). One set
 * for both themes: the theme changes tokens (radius, surface, blur, fonts), not the markup.
 * Touch targets are at least 44 × 44 px; focus is the global 3 px accent ring.
 */
import type { ComponentProps, ReactNode } from "react";

import { Link } from "@/i18n/navigation";

const base =
  "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-[var(--radius-button)] px-4 py-2.5 text-base font-bold no-underline transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-60";
const variants = {
  primary: "bg-accent text-on-accent hover:opacity-90",
  secondary: "border-2 border-accent bg-transparent text-fg hover:bg-chip",
  quiet: "bg-transparent text-fg underline underline-offset-4 hover:bg-chip",
} as const;
type Variant = keyof typeof variants;

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<"button"> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`${base} ${variants[variant]} ${className}`}
      {...props}
    />
  );
}

export function ButtonLink({
  variant = "primary",
  className = "",
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant }) {
  return (
    <Link className={`${base} ${variants[variant]} ${className}`} {...props} />
  );
}

export function Card({
  as: As = "section",
  className = "",
  children,
  ...rest
}: {
  as?: "section" | "article" | "div" | "li" | "aside";
  className?: string;
  children: ReactNode;
} & Omit<ComponentProps<"section">, "className" | "children" | "ref">) {
  return (
    <As className={`card flex flex-col gap-3 p-4 ${className}`} {...rest}>
      {children}
    </As>
  );
}

export function Chip({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={`chip ${className}`}>{children}</span>;
}

export function PageTitle({
  children,
  eyebrow,
}: {
  children: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-1">
      {eyebrow ? <p className="text-sm text-muted">{eyebrow}</p> : null}
      <h1 className="text-[length:var(--title-size)] leading-tight font-semibold">
        {children}
      </h1>
    </header>
  );
}

export function SectionTitle({
  children,
  id,
}: {
  children: ReactNode;
  id?: string;
}) {
  return (
    <h2 id={id} className="text-xl leading-snug font-semibold">
      {children}
    </h2>
  );
}

/** A small mono text for codes, ratios and ranges (IBM Plex Mono, tabular numerals). */
export function Mono({ children }: { children: ReactNode }) {
  return <span className="mono">{children}</span>;
}
