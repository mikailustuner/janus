"use client";
/**
 * The home hero (Req 27): the product sentence, "Try the demo" as the main action, and the art.
 * Isolated so the art direction (owner decision pending: bust or isometric home diorama, possibly
 * 3D) can be swapped here without touching the rest of the home page. Whatever replaces the art
 * keeps the contract: the h1 `home-title`, `Home.intro`, the demo link first, and in Two Faces the
 * art stays functional (it links to the two faces); decorative art is `aria-hidden`.
 */
import { ButtonLink } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { useT, useTheme, useThemeWord } from "@/theme/words";

const SHADOW = "var(--mask-shadow)";
const LIGHT = "var(--mask-light)";

/** One half of the mask (the left half; the right one is mirrored), with an eye hole. */
function MaskHalf({
  fill,
  stroke,
  mirror,
}: {
  fill: string;
  stroke: string;
  mirror?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 100 160"
      className="h-40 w-auto sm:h-52"
      aria-hidden
      focusable="false"
    >
      <g transform={mirror ? "translate(100 0) scale(-1 1)" : undefined}>
        <path
          fillRule="evenodd"
          style={{ fill, stroke }}
          strokeWidth="3"
          d="M100 8C44 8 6 36 6 80c0 42 44 72 94 72ZM60 62c-12 0-20 6-22 12 8 4 16 6 24 4 4-2 6-6 6-10 0-4-4-6-8-6Z"
        />
      </g>
    </svg>
  );
}

function MaskHero() {
  const w = useThemeWord();
  return (
    <nav aria-label={w("Shell.mask.label")} className="justify-self-center">
      <ul className="flex items-end">
        <li>
          <Link
            href="/start"
            className="flex flex-col items-center gap-2 rounded-l-[var(--radius-card)] p-2 font-bold no-underline"
          >
            <MaskHalf fill={SHADOW} stroke={LIGHT} />
            <span>{w("Shell.mask.patient")}</span>
          </Link>
        </li>
        <li>
          <Link
            href="/research"
            className="flex flex-col items-center gap-2 rounded-r-[var(--radius-card)] p-2 font-bold no-underline"
          >
            <MaskHalf fill={LIGHT} stroke={SHADOW} mirror />
            <span>{w("Shell.mask.research")}</span>
          </Link>
        </li>
      </ul>
    </nav>
  );
}

/** Glass: the three soft colour fields as the hero illustration (decorative). */
function Fields() {
  return (
    <div
      aria-hidden
      className="relative hidden h-64 overflow-hidden rounded-[var(--radius-card)] md:block"
    >
      <span className="absolute top-2 left-4 size-40 rounded-full bg-[var(--field-1)] blur-2xl" />
      <span className="absolute top-16 right-2 size-44 rounded-full bg-[var(--field-2)] blur-2xl" />
      <span className="absolute bottom-0 left-20 size-40 rounded-full bg-[var(--field-3)] blur-2xl" />
    </div>
  );
}

export function HomeHero() {
  const t = useT();
  const w = useThemeWord();
  const theme = useTheme();
  return (
    <section
      aria-labelledby="home-title"
      className="grid items-center gap-6 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm font-bold tracking-wide text-muted uppercase">
          {w("Home.tagline")}
        </p>
        <h1
          id="home-title"
          className="text-[length:var(--title-size)] leading-tight font-bold md:text-5xl"
        >
          {t("Home.title")}
        </h1>
        <p className="max-w-[60ch] text-lg">{t("Home.intro")}</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <ButtonLink href="/demo">{t("Home.demo")}</ButtonLink>
          <ButtonLink href="/start" variant="secondary">
            {t("Home.start")}
          </ButtonLink>
        </div>
        <p className="text-sm text-muted">{t("Home.demoHint")}</p>
      </div>
      {theme === "two-faces" ? <MaskHero /> : <Fields />}
    </section>
  );
}
