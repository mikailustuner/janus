"use client";
/**
 * Dataset export (light-face design §10, Req 4.2, DP13): one API answer, saved in the browser as
 * JSON (with licence, attribution and snapshot) or as CSV. Aggregated counts only.
 */

import { StateView } from "@/components/StateView";
import { Button, Card } from "@/components/ui";
import { useCall } from "@/flow/useCall";
import { lightClient } from "@/light/client";
import { fileName, toCsv } from "@/light/view";
import { useT } from "@/theme/words";

import { LightFrame } from "./LightFrame";

function save(name: string, type: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Export() {
  const t = useT();
  const call = useCall(() => lightClient.exportData(), []);
  const data = call.status === "ok" ? call.data : null;
  return (
    <LightFrame
      title={t("Light.export.title")}
      intro={t("Light.export.intro")}
      status={data?.status ?? null}
      snapshot={data?.snapshot ?? null}
      attribution={data?.attribution ?? []}
    >
      {call.status === "loading" ? (
        <StateView state="loading" label={t("Light.export.loading")} />
      ) : call.status === "error" ? (
        <StateView
          state="error"
          messageKey={call.error.messageKey}
          retry={call.retry}
        />
      ) : data ? (
        <Card as="section" data-testid="export-panel">
          <p className="font-bold">
            {t("Light.export.licence", { licence: data.licence })}
          </p>
          <p>{t("Light.codes.export_aggregated")}</p>
          <p className="text-sm">{t("Light.export.columns")}</p>
          <p className="mono">
            {t("Light.export.rows", { count: data.rows.length })}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() =>
                save(
                  fileName(data.snapshot.build_id, "json"),
                  "application/json",
                  JSON.stringify(data, null, 1),
                )
              }
            >
              {t("Light.export.json")}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                save(
                  fileName(data.snapshot.build_id, "csv"),
                  "text/csv",
                  toCsv(data.rows),
                )
              }
            >
              {t("Light.export.csv")}
            </Button>
          </div>
        </Card>
      ) : null}
    </LightFrame>
  );
}
