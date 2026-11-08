"use client";
/**
 * The app shell (experience design §3, §7, Req 8): header (brand, demo label and exit, mask switch
 * in Two Faces, language switcher), main content (max 720 px), footer with the disclaimer, the
 * emergency number and the secondary links, and the navigation (Two Faces: bottom bar; Glass:
 * floating pill). One component set; the theme changes tokens and a few variant classes.
 */
import { useLocale } from "next-intl";
import { useEffect, type ReactNode } from "react";

import { exitDemo, useDemo } from "@/demo/session";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { localeNames, routing } from "@/i18n/routing";
import { useStorageNotices } from "@/store/hooks";
import { faceFor } from "@/theme/prepaint";
import { useT, useTheme, useThemeWord } from "@/theme/words";

import {
  FacesIcon,
  GlobeIcon,
  PillIcon,
  ResultsIcon,
  ScanIcon,
  SettingsIcon,
} from "./icons";
import { useUserRegion } from "./region";

/** Keeps `data-face` in step with the route after client navigation (DP18). */
function FaceSync() {
  const pathname = usePathname();
  const locale = useLocale();
  useEffect(() => {
    document.documentElement.dataset.face = faceFor(
      `/${locale}${pathname === "/" ? "" : pathname}`,
    );
  }, [pathname, locale]);
  return null;
}

function LanguageSwitcher() {
  const t = useT();
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  return (
    <label className="relative flex min-h-11 items-center gap-1 rounded-full px-2 text-sm">
      <GlobeIcon size={20} />
      <span className="sr-only">{t("LocaleSwitcher.label")}</span>
      <select
        value={locale}
        onChange={(e) =>
          router.replace(
            // Keep the fragment (a finding's position, a demo fragment); never a query string.
            pathname + (typeof location === "undefined" ? "" : location.hash),
            { locale: e.target.value as (typeof routing.locales)[number] },
          )
        }
        className="min-h-11 cursor-pointer appearance-none bg-transparent pr-1 font-bold text-fg"
      >
        {routing.locales.map((l) => (
          <option key={l} value={l} lang={l} className="bg-bg text-fg">
            {localeNames[l]}
          </option>
        ))}
      </select>
    </label>
  );
}

function MaskSwitch({ research }: { research: boolean }) {
  const w = useThemeWord();
  return (
    <nav aria-label={w("Shell.mask.label")}>
      <ul className="flex overflow-hidden rounded-full border-2 border-accent text-sm">
        <li>
          <Link
            href="/"
            aria-current={research ? undefined : "page"}
            className={`flex min-h-11 items-center px-3 font-bold no-underline ${research ? "text-fg" : "bg-accent text-on-accent"}`}
          >
            {w("Shell.mask.patient")}
          </Link>
        </li>
        <li>
          <Link
            href="/research"
            aria-current={research ? "page" : undefined}
            className={`flex min-h-11 items-center px-3 font-bold no-underline ${research ? "bg-accent text-on-accent" : "text-fg"}`}
          >
            {w("Shell.mask.research")}
          </Link>
        </li>
      </ul>
    </nav>
  );
}

function DemoBar() {
  const t = useT();
  const demo = useDemo();
  const router = useRouter();
  if (!demo) return null;
  return (
    <div
      data-testid="demo-label"
      className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-card)] bg-chip px-3 py-1 text-chip-fg"
    >
      <p className="text-sm font-bold tracking-wide uppercase">
        {t("Demo.labelWith", { patient: t(`Demo.patients.${demo}.name`) })}
      </p>
      <button
        type="button"
        onClick={() => {
          exitDemo();
          router.push("/");
        }}
        className="min-h-11 rounded-full px-3 text-sm font-bold underline underline-offset-4"
      >
        {t("Demo.exit")}
      </button>
    </div>
  );
}

const NAV = [
  { href: "/scan", key: "scan", Icon: ScanIcon },
  { href: "/medicines", key: "medicines", Icon: PillIcon },
  { href: "/results", key: "results", Icon: ResultsIcon },
  { href: "/settings", key: "settings", Icon: SettingsIcon },
] as const;

function Nav() {
  const t = useT();
  const theme = useTheme();
  const pathname = usePathname();
  const glass = theme === "glass";
  return (
    <nav
      aria-label={t("Shell.navLabel")}
      className={
        glass
          ? "fixed inset-x-3.5 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-20 mx-auto max-w-[720px] rounded-full border border-[var(--card-edge)] bg-surface shadow-[var(--card-shadow)] [backdrop-filter:var(--blur)] no-print"
          : "fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] no-print"
      }
    >
      <ul className="mx-auto grid max-w-[720px] grid-cols-4">
        {NAV.map(({ href, key, Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={key}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-xs font-bold no-underline ${
                  active
                    ? glass
                      ? "m-1 rounded-full bg-chip text-chip-fg"
                      : "text-accent"
                    : "text-muted"
                }`}
              >
                <Icon size={24} />
                {t(`Shell.nav.${key}`)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function StorageNotice() {
  const t = useT();
  const notices = useStorageNotices();
  if (notices.size === 0) return null;
  return (
    <div role="status" className="card p-3 text-sm">
      {[...notices].map((n) => (
        <p key={n}>{t(`Storage.${n}`)}</p>
      ))}
    </div>
  );
}

function Footer() {
  const t = useT();
  const w = useThemeWord();
  const region = useUserRegion();
  return (
    <footer className="mx-auto mt-10 flex w-full max-w-[720px] flex-col gap-2 border-t border-line px-4 pt-4 pb-[calc(6.5rem+env(safe-area-inset-bottom))] text-sm text-muted">
      <p data-testid="disclaimer">{t("Disclaimer.text")}</p>
      <p>
        {t("Emergency.short", { emergency: t(`Memory.emergency.${region}`) })}
      </p>
      <ul className="flex flex-wrap gap-x-2">
        <li>
          <Link
            href="/research"
            className="inline-flex min-h-11 items-center px-1 underline underline-offset-4"
          >
            {w("Shell.nav.research")}
          </Link>
        </li>
        <li>
          <Link
            href="/demo/codes"
            className="inline-flex min-h-11 items-center px-1 underline underline-offset-4"
          >
            {t("Shell.demoCodes")}
          </Link>
        </li>
        <li>
          <Link
            href="/privacy"
            className="inline-flex min-h-11 items-center px-1 underline underline-offset-4"
          >
            {t("Shell.privacy")}
          </Link>
        </li>
        <li>
          <Link
            href="/donate"
            className="inline-flex min-h-11 items-center px-1 underline underline-offset-4"
          >
            {t("Shell.donate")}
          </Link>
        </li>
      </ul>
    </footer>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const t = useT();
  const theme = useTheme();
  const pathname = usePathname();
  const research =
    pathname === "/research" || pathname.startsWith("/research/");
  return (
    <>
      <FaceSync />
      <a
        href="#content"
        className="sr-only z-30 rounded-[var(--radius-button)] bg-accent px-4 py-3 font-bold text-on-accent focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t("Shell.skip")}
      </a>
      <header className="mx-auto flex w-full max-w-[720px] flex-col gap-2 px-4 pt-3 no-print">
        <div className="flex items-center justify-between gap-2">
          <Link
            href="/"
            className="flex min-h-11 items-center gap-2 font-display text-xl font-semibold no-underline"
          >
            <FacesIcon size={22} />
            Janus
          </Link>
          <div className="flex items-center gap-1">
            {theme === "two-faces" ? <MaskSwitch research={research} /> : null}
            <LanguageSwitcher />
          </div>
        </div>
        <DemoBar />
        <StorageNotice />
      </header>
      <main
        id="content"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-[720px] flex-col gap-5 px-4 pt-4 outline-none"
      >
        {children}
      </main>
      <Footer />
      <Nav />
    </>
  );
}
