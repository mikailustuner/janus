"use client";
import { PageTitle, SectionTitle } from "@/components/ui";
import codes from "@/demo/codes.svg.json";
import { PATIENTS } from "@/demo/session";
import { useT } from "@/theme/words";

type Code = {
  patient: string;
  index: number;
  text: string;
  boxName: string;
  ndc: string | null;
  svg: string;
};

/** The printable demo sheet (design §13.2, Req 4.2): one code per demo product, labelled DEMO. */
export function DemoSheet() {
  const t = useT();
  const all = Object.entries(codes as Record<string, Code>);
  return (
    <>
      <PageTitle eyebrow={t("Demo.label")}>{t("Demo.codes")}</PageTitle>
      <p>{t("Demo.codesIntro")}</p>
      <p className="text-sm text-muted">{t("Demo.serialNote")}</p>
      {PATIENTS.map((p) => (
        <section
          key={p}
          className="flex flex-col gap-3"
          aria-labelledby={`sheet-${p}`}
        >
          <SectionTitle id={`sheet-${p}`}>
            {t(`Demo.patients.${p}.name`)}
          </SectionTitle>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {all
              .filter(([, c]) => c.patient === p)
              .map(([gtin, c]) => (
                <li
                  key={gtin}
                  className="card flex items-center gap-4 p-3 break-inside-avoid"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- inline SVG data, no network */}
                  <img
                    src={`data:image/svg+xml;utf8,${encodeURIComponent(c.svg)}`}
                    alt={`DataMatrix ${gtin}`}
                    width={96}
                    height={96}
                    className="shrink-0 rounded bg-[var(--surface)] [image-rendering:pixelated]"
                  />
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="font-bold">{c.boxName}</p>
                    <p className="mono text-sm">{gtin}</p>
                    {c.ndc ? (
                      <p className="mono text-sm">NDC {c.ndc} DEMO</p>
                    ) : null}
                    <p className="text-sm font-bold text-warn">
                      {t("Demo.codeLabel")}
                    </p>
                  </div>
                </li>
              ))}
          </ul>
        </section>
      ))}
    </>
  );
}
