import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";

import { routing } from "@/i18n/routing";
import { OG_SIZE, translator } from "@/seo/metadata";
import { OG_COLORS as C } from "@/theme/og";

// The social image: the Janus name and a one-line tagline in the Night Pharmacy tokens. Static
// per locale, generated at build time. No claim about health, no assessment.
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

const font = (file: string) =>
  readFile(join(process.cwd(), "public/fonts", file));

async function render(locale: string): Promise<ArrayBuffer> {
  "use cache";
  const t = await translator(locale);
  const [display, text] = await Promise.all([
    font("Fraunces-SemiBold.ttf"),
    font("AtkinsonHyperlegibleNext-Regular.ttf"),
  ]);
  const image = new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 80,
        background: C.bg,
        color: C.fg,
        fontFamily: "Atkinson",
      }}
    >
      <svg width="96" height="96" viewBox="0 0 64 64">
        <circle
          cx="32"
          cy="32"
          r="20"
          fill="none"
          stroke={C.fg}
          strokeWidth="4"
        />
        <path d="M32 12a20 20 0 0 0 0 40Z" fill={C.fg} />
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <div
          style={{
            fontFamily: "Fraunces",
            fontSize: 168,
            lineHeight: 1,
            letterSpacing: -2,
          }}
        >
          {t("Metadata.title")}
        </div>
        <div style={{ width: 120, height: 8, background: C.accent }} />
        <div style={{ fontSize: 52, lineHeight: 1.25, color: C.muted }}>
          {t("Home.tagline.glass")}
        </div>
      </div>
      <div style={{ fontSize: 30, color: C.accent }}>janusmeds.org</div>
    </div>,
    {
      ...OG_SIZE,
      fonts: [
        { name: "Fraunces", data: display, weight: 600, style: "normal" },
        { name: "Atkinson", data: text, weight: 400, style: "normal" },
      ],
    },
  );
  return image.arrayBuffer();
}

export async function GET(
  _request: Request,
  { params }: RouteContext<"/[locale]/og.png">,
) {
  const { locale } = await params;
  return new Response(await render(locale), {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=3600, s-maxage=86400",
    },
  });
}
