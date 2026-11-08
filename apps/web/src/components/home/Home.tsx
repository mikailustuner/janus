"use client";
import { EmergencyNotice } from "@/components/EmergencyNotice";
import { ReminderCard } from "@/components/loop/ReminderCard";
import { ButtonLink, Card, PageTitle } from "@/components/ui";
import { useDemo } from "@/demo/session";
import { useList } from "@/store/hooks";
import { useT, useThemeWord } from "@/theme/words";

/** Home (design §3, §9): the emergency notice first, then the way in. */
export function Home() {
  const t = useT();
  const w = useThemeWord();
  const { ready, value } = useList();
  const demo = useDemo();
  const count = value.items.length;
  return (
    <>
      <EmergencyNotice />
      <ReminderCard />
      <PageTitle eyebrow={w("Home.tagline")}>{t("Home.title")}</PageTitle>
      <p className="text-lg">{t("Home.intro")}</p>
      {ready && count > 0 && !demo ? (
        <Card>
          <p className="font-bold">{t("Home.resume")}</p>
          <p className="text-muted">{t("Home.resumeCount", { count })}</p>
          <ButtonLink href="/medicines" className="self-start">
            {t("Medicines.title")}
          </ButtonLink>
        </Card>
      ) : null}
      <div className="flex flex-col gap-3 sm:flex-row">
        <ButtonLink href="/start">{t("Home.start")}</ButtonLink>
        <ButtonLink href="/demo" variant="secondary">
          {t("Home.demo")}
        </ButtonLink>
      </div>
      <p className="text-sm text-muted">{t("Home.demoHint")}</p>
    </>
  );
}
