"use client";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import type { Locale } from "@/api/contracts";

import { load, type Loaded } from "./index";

/** The vocabulary of the interface language, or null while its chunk loads. */
export function useVocabulary(locale?: Locale): Loaded | null {
  const current = useLocale() as Locale;
  const lang = locale ?? current;
  const [v, setV] = useState<Loaded | null>(null);
  useEffect(() => {
    let live = true;
    load(lang).then(
      (x) => live && setV(x),
      () => live && setV(null),
    );
    return () => {
      live = false;
    };
  }, [lang]);
  return v && v.locale === lang ? v : null;
}
