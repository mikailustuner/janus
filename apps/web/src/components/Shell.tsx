"use client";
/**
 * The app shell (experience design §3, §7, Req 8): header (brand, demo label and exit, mask switch
 * in Two Faces, language switcher), main content (max 720 px), footer with the disclaimer, the
 * emergency number and the secondary links, and the navigation (Two Faces: bottom bar; Glass:
 * floating pill). One component set; the theme changes tokens and a few variant classes.
 */
import { useLocale } from "next-intl";
import { useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";

import { exitDemo, useDemo } from "@/demo/session";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { localeNames, routing } from "@/i18n/routing";
import { updateSettings, useStorageNotices } from "@/store/hooks";
import { faceFor } from "@/theme/prepaint";
import { useT, useTheme, useThemeWord } from "@/theme/words";

import {
  FacesIcon,
  GlobeIcon,
  PassportIcon,
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
  { href: "/passport", key: "passport", Icon: PassportIcon },
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
          ? "fixed inset-x-3.5 bottom-[calc(1rem+env(safe-area-inset-bottom))] z-20 mx-auto max-w-[720px] rounded-full border border-[var(--card-edge)] bg-surface shadow-[var(--card-shadow)] [backdrop-filter:var(--blur)] no-print md:hidden"
          : "fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] no-print md:hidden"
      }
    >
      <ul className="mx-auto grid max-w-[720px] grid-cols-5">
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
                <span className="max-w-full text-center [overflow-wrap:anywhere] hyphens-auto">
                  {t(`Shell.nav.${key}`)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Header navigation from 768 px (Req 27.1): the same four places, plus Research in Glass. */
function HeaderNav() {
  const t = useT();
  const w = useThemeWord();
  const theme = useTheme();
  const pathname = usePathname();
  const items: { href: string; label: string }[] = [
    ...NAV.map(({ href, key }) => ({ href, label: t(`Shell.nav.${key}`) })),
    ...(theme === "glass"
      ? [{ href: "/research", label: w("Shell.nav.research") }]
      : []),
  ];
  return (
    <nav aria-label={t("Shell.navLabel")} className="hidden md:block">
      <ul className="flex items-center gap-1">
        {items.map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center rounded-full px-3 font-bold no-underline ${active ? "bg-chip text-chip-fg" : "text-fg hover:bg-chip"}`}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Theme control in the header (Req 27.1): Two Faces ↔ Glass; Settings › Appearance has the rest. */
function ThemeToggle() {
  const t = useT();
  const theme = useTheme();
  const next = theme === "glass" ? "two-faces" : "glass";
  return (
    <button
      type="button"
      onClick={() => updateSettings({ theme: next })}
      className="hidden min-h-11 items-center rounded-full px-3 text-sm font-bold hover:bg-chip md:flex"
      aria-label={`${t("Settings.theme")}: ${t(theme === "glass" ? "Settings.themeGlass" : "Settings.themeTwoFaces")}`}
    >
      {t(theme === "glass" ? "Settings.themeGlass" : "Settings.themeTwoFaces")}
    </button>
  );
}

/** Routes laid out as a wide website page from 1024 px (Req 27.2–27.4, DP41). */
const WIDE = [
  "/",
  "/results",
  "/medicines",
  "/memory",
  "/note",
  "/settings",
  "/passport",
  "/passport/item",
];

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
    <footer className="mx-auto mt-10 flex w-full max-w-[720px] flex-col gap-2 border-t border-line px-4 pt-4 pb-[calc(6.5rem+env(safe-area-inset-bottom))] text-sm text-muted md:max-w-[1120px] md:pb-8">
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

const onScroll = (l: () => void) => {
  addEventListener("scroll", l, { passive: true });
  return () => removeEventListener("scroll", l);
};

/** True once the page is scrolled (the home header turns to glass). */
function useScrolled(): boolean {
  return useSyncExternalStore(
    onScroll,
    () => scrollY > 8,
    () => false,
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const t = useT();
  const theme = useTheme();
  const pathname = usePathname();
  const research =
    pathname === "/research" || pathname.startsWith("/research/");
  const wide = WIDE.includes(pathname);
  const home = pathname === "/";
  const scrolled = useScrolled();
  const header = useRef<HTMLElement>(null);
  // The home's emergency bar sits under the header, whatever its height (demo bar, notices).
  useEffect(() => {
    const el = header.current;
    if (!home || !el) return;
    const root = document.documentElement;
    const ro = new ResizeObserver(() =>
      root.style.setProperty("--home-header-h", `${el.offsetHeight}px`),
    );
    ro.observe(el);
    return () => {
      ro.disconnect();
      root.style.removeProperty("--home-header-h");
    };
  }, [home]);
  return (
    <>
      <FaceSync />
      <a
        href="#content"
        className="sr-only z-30 rounded-[var(--radius-button)] bg-accent px-4 py-3 font-bold text-on-accent focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t("Shell.skip")}
      </a>
      {/* The home is one scene: its header lies over the hero, glass once scrolled (DP46). */}
      <header
        ref={header}
        className={
          home
            ? `home-header no-print ${scrolled ? "home-header-scrolled" : ""}`
            : undefined
        }
      >
        <div
          className={`mx-auto flex w-full ${wide ? "max-w-[720px] lg:max-w-[1120px]" : "max-w-[720px] md:max-w-[1120px]"} flex-col gap-2 px-4 pt-3 ${home ? "pb-2" : ""} no-print`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link
              href="/"
              className="flex min-h-11 items-center gap-2 font-display text-xl font-semibold no-underline"
            >
              <FacesIcon size={22} />
              Janus
            </Link>
            <HeaderNav />
            <div className="flex items-center gap-1">
              {theme === "two-faces" ? (
                <MaskSwitch research={research} />
              ) : null}
              <ThemeToggle />
              <LanguageSwitcher />
            </div>
          </div>
          <DemoBar />
          <StorageNotice />
        </div>
      </header>
      <main
        id="content"
        tabIndex={-1}
        className={
          home
            ? "flex w-full flex-col gap-5 outline-none"
            : `mx-auto flex w-full max-w-[720px] flex-col gap-5 px-4 pt-4 outline-none ${wide ? "lg:max-w-[1120px]" : ""}`
        }
      >
        {children}
      </main>
      <Footer />
      <Nav />
    </>
  );
}
