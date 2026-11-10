/**
 * On-device text recognition (experience design §6.4, DP9, DP10; ocr-first design §4): a
 * tesseract.js worker made on demand with its worker, core and tessdata_fast models served from
 * /vendor/tesseract. The photo and the recognised text never leave the device; the photo is
 * dropped when it has been read.
 */
import type { Locale } from "@/api/contracts";

import { readLabel, type Pass, type Turns } from "./ocr-passes";

const LANG: Record<Locale, string> = {
  en: "eng",
  tr: "tur",
  de: "deu",
  fr: "fra",
  es: "spa",
};

export type Recognised = Pass;

/** A phone photo is far larger than the recogniser needs; the long side is limited to this. */
const MAX_SIDE = 2600;

/** The photo turned by quarter turns and limited in size, as a PNG. */
async function prepare(image: Blob, turns: Turns): Promise<Blob> {
  const bmp = await createImageBitmap(image);
  try {
    const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
    if (turns === 0 && scale === 1) return image;
    const w = Math.round(bmp.width * scale);
    const h = Math.round(bmp.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = turns % 2 === 1 ? h : w;
    canvas.height = turns % 2 === 1 ? w : h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return image;
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((turns * Math.PI) / 2);
    ctx.drawImage(bmp, -w / 2, -h / 2, w, h);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("canvas"))),
        "image/png",
      ),
    );
  } finally {
    bmp.close();
  }
}

/**
 * Reads a label photo. `useful` says whether a reading names something to offer; a reading that
 * does not, and that the recogniser is not confident about, is tried again turned
 * (`ocr-passes.ts`). `onProgress` gets the progress of the current reading and whether it is a
 * turned one.
 */
export async function recognise(
  image: Blob,
  locale: Locale,
  useful: (pass: Pass) => boolean,
  onProgress?: (p: number, turned: boolean) => void,
): Promise<Recognised> {
  const { createWorker } = await import("tesseract.js");
  let turned = false;
  // The interface language first, then English (labels often mix both).
  const langs = locale === "en" ? ["eng"] : [LANG[locale], "eng"];
  const worker = await createWorker(langs, 1, {
    workerPath: "/vendor/tesseract/worker.min.js",
    corePath: "/vendor/tesseract/core",
    langPath: "/vendor/tesseract/lang",
    gzip: false,
    cacheMethod: "none",
    logger: (m: { status: string; progress: number }) => {
      if (m.status === "recognizing text") onProgress?.(m.progress, turned);
    },
  });
  try {
    return await readLabel(async (turns) => {
      turned = turns !== 0;
      const { data } = await worker.recognize(
        await prepare(image, turns),
        { rotateAuto: true },
        { blocks: true },
      );
      const lines: Pass["lines"] = [];
      for (const b of data.blocks ?? [])
        for (const p of b.paragraphs)
          for (const l of p.lines)
            lines.push({
              text: l.text.trim(),
              words: l.words.map((w) => w.text).filter(Boolean),
            });
      return {
        confidence: data.confidence,
        lines: lines.filter((l) => l.text),
      };
    }, useful);
  } finally {
    await worker.terminate();
  }
}
