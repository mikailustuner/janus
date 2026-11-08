/** Settings document `janus.v1.settings` (experience design §4.1, Req 9.1, 9.2). */
import type {
  Locale,
  LoopRegion,
  ScanRegion,
  UserRegion,
} from "@/api/contracts";

import { Doc, PREFIX, storage, type SafeStorage } from "./storage";

export type Theme = "two-faces" | "glass";

export interface Settings {
  v: 1;
  theme: Theme;
  largeText: boolean;
  reduceTransparency: boolean;
  readAloud: boolean;
  noteLanguage: Locale | null; // null: same as the interface language
  scanRegion: ScanRegion | null;
  userRegion: UserRegion;
  statisticsRegion: LoopRegion | null;
}

export const DEFAULT_SETTINGS: Settings = {
  v: 1,
  theme: "two-faces",
  largeText: false,
  reduceTransparency: false,
  readAloud: false,
  noteLanguage: null,
  scanRegion: null,
  userRegion: "UNKNOWN",
  statisticsRegion: null,
};

const LOCALES = ["en", "tr", "de", "fr", "es"];
const oneOf = <T>(
  v: unknown,
  values: readonly unknown[],
  nullable = false,
): v is T => (nullable && v === null) || values.includes(v);

/** Validates a stored settings document; a field the client does not know is ignored. */
export function validateSettings(v: unknown): Settings | null {
  if (typeof v !== "object" || v === null) return null;
  const o = v as Record<string, unknown>;
  if (o.v !== 1) return null;
  const s = { ...DEFAULT_SETTINGS };
  for (const k of ["largeText", "reduceTransparency", "readAloud"] as const) {
    if (k in o) {
      if (typeof o[k] !== "boolean") return null;
      s[k] = o[k] as boolean;
    }
  }
  if ("theme" in o) {
    if (!oneOf<Theme>(o.theme, ["two-faces", "glass"])) return null;
    s.theme = o.theme;
  }
  if ("noteLanguage" in o) {
    if (!oneOf<Locale | null>(o.noteLanguage, LOCALES, true)) return null;
    s.noteLanguage = o.noteLanguage;
  }
  if ("scanRegion" in o) {
    if (!oneOf<ScanRegion | null>(o.scanRegion, ["TR", "US", "EU"], true))
      return null;
    s.scanRegion = o.scanRegion;
  }
  if ("userRegion" in o) {
    if (
      !oneOf<UserRegion>(o.userRegion, ["US", "TR", "EU", "OTHER", "UNKNOWN"])
    )
      return null;
    s.userRegion = o.userRegion;
  }
  if ("statisticsRegion" in o) {
    if (!oneOf<LoopRegion | null>(o.statisticsRegion, ["TR", "EU", "US"], true))
      return null;
    s.statisticsRegion = o.statisticsRegion;
  }
  return s;
}

export function settingsDoc(store: SafeStorage = storage) {
  return new Doc<Settings>(
    store,
    `${PREFIX}settings`,
    validateSettings,
    () => ({
      ...DEFAULT_SETTINGS,
    }),
  );
}

export const settings = settingsDoc();
