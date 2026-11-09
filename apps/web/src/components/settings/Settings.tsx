"use client";
import { useLocale } from "next-intl";
import { useState } from "react";

import type {
  Locale,
  LoopRegion,
  ScanRegion,
  UserRegion,
} from "@/api/contracts";
import { RadioGroup, SelectField, Switch } from "@/components/Field";
import {
  Button,
  ButtonLink,
  Card,
  PageTitle,
  SectionTitle,
} from "@/components/ui";
import { ZombieSettings } from "@/components/zombie/Zombie";
import { usePathname, useRouter } from "@/i18n/navigation";
import { localeNames, routing } from "@/i18n/routing";
import { deleteEverything, updateSettings, useSettings } from "@/store/hooks";
import { useT } from "@/theme/words";

const USER: UserRegion[] = ["TR", "EU", "US", "OTHER", "UNKNOWN"];

/** Settings (Req 9.1): languages, regions, Appearance, read aloud, delete everything. */
export function Settings() {
  const t = useT();
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const { value } = useSettings();
  const [confirming, setConfirming] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const names = routing.locales.map((l) => ({
    value: l,
    label: localeNames[l],
    lang: l,
  }));

  return (
    <>
      <PageTitle>{t("Settings.title")}</PageTitle>
      {/* Desktop (Req 27): language and regions on the left, appearance and data on the right. */}
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <SelectField
              label={t("Settings.language")}
              value={locale}
              options={names}
              onChange={(l) => router.replace(pathname, { locale: l })}
            />
            <SelectField
              label={t("Settings.noteLanguage")}
              value={value.noteLanguage ?? "same"}
              options={[
                { value: "same", label: t("Settings.noteLanguageSame") },
                ...names,
              ]}
              onChange={(l) =>
                updateSettings({
                  noteLanguage: l === "same" ? null : (l as Locale),
                })
              }
            />
          </Card>

          <Card>
            <SectionTitle>{t("Settings.regions")}</SectionTitle>
            <SelectField
              label={t("Settings.scanRegion")}
              value={value.scanRegion ?? "auto"}
              options={[
                { value: "auto", label: t("Settings.scanRegionAuto") },
                ...(["TR", "US", "EU"] as const).map((r) => ({
                  value: r,
                  label: t(`Common.region.${r}`),
                })),
              ]}
              onChange={(v) =>
                updateSettings({
                  scanRegion: v === "auto" ? null : (v as ScanRegion),
                })
              }
            />
            <SelectField
              label={t("Settings.userRegion")}
              value={value.userRegion}
              options={USER.map((r) => ({
                value: r,
                label: t(`Common.region.${r}`),
              }))}
              onChange={(v) => updateSettings({ userRegion: v })}
            />
            <SelectField
              label={t("Settings.statisticsRegion")}
              value={value.statisticsRegion ?? "none"}
              options={[
                { value: "none", label: t("Settings.statisticsRegionNone") },
                ...(["TR", "EU", "US"] as const).map((r) => ({
                  value: r,
                  label: t(`Common.region.${r}`),
                })),
              ]}
              onChange={(v) =>
                updateSettings({
                  statisticsRegion: v === "none" ? null : (v as LoopRegion),
                })
              }
            />
          </Card>
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <SectionTitle>{t("Settings.appearance")}</SectionTitle>
            <RadioGroup
              legend={t("Settings.theme")}
              name="theme"
              value={value.theme}
              options={[
                {
                  value: "two-faces",
                  label: t("Settings.themeTwoFaces"),
                  hint: t("Settings.themeTwoFacesHint"),
                },
                {
                  value: "glass",
                  label: t("Settings.themeGlass"),
                  hint: t("Settings.themeGlassHint"),
                },
              ]}
              onChange={(theme) => updateSettings({ theme })}
            />
            <Switch
              label={t("Settings.largeText")}
              checked={value.largeText}
              onChange={(largeText) => updateSettings({ largeText })}
            />
            <Switch
              label={t("Settings.reduceTransparency")}
              hint={t("Settings.reduceTransparencyHint")}
              checked={value.reduceTransparency}
              onChange={(reduceTransparency) =>
                updateSettings({ reduceTransparency })
              }
            />
            <Switch
              label={t("Settings.readAloud")}
              hint={t("Settings.readAloudHint")}
              checked={value.readAloud}
              onChange={(readAloud) => updateSettings({ readAloud })}
            />
          </Card>

          <ZombieSettings />

          <Card>
            <ButtonLink
              href="/research"
              variant="secondary"
              className="self-start"
            >
              {t("Shell.nav.research")}
            </ButtonLink>
          </Card>

          <Card>
            <SectionTitle>{t("Settings.deleteTitle")}</SectionTitle>
            <p>{t("Settings.deleteBody")}</p>
            {deleted ? (
              <p role="status" className="font-bold">
                {t("Settings.deleteDone")}
              </p>
            ) : confirming ? (
              <div
                className="flex flex-col gap-3"
                role="alertdialog"
                aria-label={t("Settings.deleteTitle")}
              >
                <p className="font-bold">{t("Settings.deleteConfirm")}</p>
                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={async () => {
                      await deleteEverything();
                      setConfirming(false);
                      setDeleted(true);
                    }}
                  >
                    {t("Settings.deleteButton")}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setConfirming(false)}
                  >
                    {t("Common.cancel")}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="secondary"
                className="self-start"
                onClick={() => setConfirming(true)}
              >
                {t("Settings.deleteButton")}
              </Button>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
