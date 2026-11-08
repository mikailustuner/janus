"use client";
import type { ScanRegion, UserRegion } from "@/api/contracts";
import { RadioGroup } from "@/components/Field";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
import { updateSettings, useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

const SCAN = ["TR", "US", "EU", "auto"] as const;
const USER: UserRegion[] = ["TR", "EU", "US", "OTHER", "UNKNOWN"];

/** Start (design §3): scan regions and the user region (emergency numbers follow). */
export function Start() {
  const t = useT();
  const { value } = useSettings();
  return (
    <>
      <PageTitle>{t("Start.title")}</PageTitle>
      <p>{t("Start.intro")}</p>
      <Card>
        <RadioGroup
          legend={t("Start.scanRegion")}
          name="scanRegion"
          value={value.scanRegion ?? "auto"}
          options={SCAN.map((r) => ({
            value: r,
            label:
              r === "auto"
                ? t("Start.scanRegionAuto")
                : t(`Common.region.${r}`),
          }))}
          onChange={(v) =>
            updateSettings({
              scanRegion: v === "auto" ? null : (v as ScanRegion),
            })
          }
        />
      </Card>
      <Card>
        <RadioGroup
          legend={t("Start.userRegion")}
          hint={t("Start.userRegionHint")}
          name="userRegion"
          value={value.userRegion}
          options={USER.map((r) => ({
            value: r,
            label:
              r === "OTHER"
                ? t("Start.userRegionOther")
                : r === "UNKNOWN"
                  ? t("Start.userRegionUnknown")
                  : t(`Common.region.${r}`),
          }))}
          onChange={(v) => updateSettings({ userRegion: v })}
        />
      </Card>
      <ButtonLink href="/scan" className="self-start">
        {t("Start.continue")}
      </ButtonLink>
    </>
  );
}
