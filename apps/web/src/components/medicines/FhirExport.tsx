"use client";
/**
 * "Export as FHIR" (fhir-export design §4, Req 5): the list as a FHIR R4 file, built and saved in
 * the browser. Nothing is sent. Product names are off by default and the choice is not stored
 * (DP5).
 */
import { useId, useState } from "react";

import { Button, Card, SectionTitle } from "@/components/ui";
import {
  buildBundle,
  exportSummary,
  FHIR_MIME,
  fileName,
  serialise,
} from "@/fhir/bundle";
import type { Item } from "@/store/list";
import { useT } from "@/theme/words";
import type { Loaded } from "@/vocabulary";

const uuid = () => crypto.randomUUID();

function save(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: FHIR_MIME }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function FhirExport({
  items,
  vocab,
  demo,
}: {
  items: Item[];
  vocab: Loaded;
  demo: boolean;
}) {
  const t = useT();
  const id = useId();
  const [names, setNames] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const s = exportSummary(items);
  return (
    <Card aria-labelledby={`${id}-title`} data-testid="fhir-export">
      <SectionTitle id={`${id}-title`}>{t("Fhir.title")}</SectionTitle>
      <p>{t("Fhir.what")}</p>
      {demo ? <p className="text-sm text-muted">{t("Fhir.demo")}</p> : null}
      <p className="font-bold" data-testid="fhir-preview">
        {t("Fhir.preview", {
          medicines: s.medicines,
          coded: s.coded,
          ingredients: s.ingredients,
        })}
      </p>
      <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-[var(--radius-button)] px-2 py-2 hover:bg-chip">
        <input
          type="checkbox"
          checked={names}
          onChange={(e) => {
            setNames(e.target.checked);
            setSaved(null);
          }}
          aria-describedby={`${id}-hint`}
          className="mt-0.5 size-6 shrink-0 cursor-pointer accent-[var(--accent)]"
        />
        <span className="flex flex-col">
          <span className="font-bold">{t("Fhir.includeNames")}</span>
          <span id={`${id}-hint`} className="text-sm text-muted">
            {t("Fhir.includeNamesHint")}
          </span>
        </span>
      </label>
      <div className="flex flex-col items-start gap-2">
        <Button
          onClick={() => {
            const now = new Date();
            const english = vocab.index.english_names;
            const bundle = buildBundle(items, {
              includeProductNames: names,
              demo,
              now,
              newId: uuid,
              englishName: (key) => english[key] ?? null,
            });
            const file = fileName(now);
            save(file, serialise(bundle));
            setSaved(file);
          }}
        >
          {t("Fhir.download")}
        </Button>
        <p role="status" className="text-sm font-bold [overflow-wrap:anywhere]">
          {saved ? t("Fhir.saved", { file: saved }) : null}
        </p>
      </div>
      <p className="text-sm text-muted">{t("Fhir.contents")}</p>
      <p className="text-sm text-muted">{t("Fhir.notSent")}</p>
      <p className="text-sm text-muted">{t("Fhir.notChecked")}</p>
    </Card>
  );
}
