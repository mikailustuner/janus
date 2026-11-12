import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "tr", "de", "fr", "es", "pt"],
  defaultLocale: "en",
});

/** Language names in their own language, for the language switcher. */
export const localeNames: Record<(typeof routing.locales)[number], string> = {
  en: "English",
  tr: "Türkçe",
  de: "Deutsch",
  fr: "Français",
  es: "Español",
  pt: "Português",
};
