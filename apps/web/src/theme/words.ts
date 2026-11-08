"use client";
/**
 * Theme vocabulary (experience design §7, DP21): messages with paired keys `<key>.twoFaces` and
 * `<key>.glass`, selected by the theme setting. Glass values never hold a theme-device word (P12).
 */
import { useTranslations } from "next-intl";
import { createContext, useContext } from "react";

import { useSettings } from "@/store/hooks";

export type Translate = (
  key: string,
  values?: Record<string, string | number>,
) => string;

/** An untyped view of the translator for keys built at run time (codes from the API). */
export function useT(): Translate {
  return useTranslations() as unknown as Translate;
}

/** Lets a test or a preview render a component in a given theme without the settings store. */
export const ThemeOverride = createContext<"two-faces" | "glass" | null>(null);

export function useTheme() {
  const override = useContext(ThemeOverride);
  const stored = useSettings().value.theme;
  return override ?? stored;
}

/** `w("Findings.title")` → the Two Faces or the Glass wording of that key. */
export function useThemeWord(): Translate {
  const t = useT();
  const theme = useTheme();
  return (key, values) =>
    t(`${key}.${theme === "glass" ? "glass" : "twoFaces"}`, values);
}
