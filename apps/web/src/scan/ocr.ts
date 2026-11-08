/**
 * On-device text recognition (experience design §6.4, DP9, DP10): a tesseract.js worker made on
 * demand with its worker, core and tessdata_fast models served from /vendor/tesseract. The photo
 * and the recognised text never leave the device and are dropped when the screen closes.
 */
import type { Locale } from "@/api/contracts";

const LANG: Record<Locale, string> = {
  en: "eng",
  tr: "tur",
  de: "deu",
  fr: "fra",
  es: "spa",
};

export interface Recognised {
  lines: { text: string; words: string[] }[];
}

export async function recognise(
  image: Blob,
  locale: Locale,
  onProgress?: (p: number) => void,
): Promise<Recognised> {
  const { createWorker } = await import("tesseract.js");
  // The interface language first, then English (labels often mix both).
  const langs = locale === "en" ? ["eng"] : [LANG[locale], "eng"];
  const worker = await createWorker(langs, 1, {
    workerPath: "/vendor/tesseract/worker.min.js",
    corePath: "/vendor/tesseract/core",
    langPath: "/vendor/tesseract/lang",
    gzip: false,
    cacheMethod: "none",
    logger: (m: { status: string; progress: number }) => {
      if (m.status === "recognizing text") onProgress?.(m.progress);
    },
  });
  try {
    const { data } = await worker.recognize(image, {}, { blocks: true });
    const lines: Recognised["lines"] = [];
    for (const b of data.blocks ?? [])
      for (const p of b.paragraphs)
        for (const l of p.lines)
          lines.push({
            text: l.text.trim(),
            words: l.words.map((w) => w.text).filter(Boolean),
          });
    return { lines: lines.filter((l) => l.text) };
  } finally {
    await worker.terminate();
  }
}
