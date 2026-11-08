"use client";
import { Button, Card, PageTitle } from "@/components/ui";
import { PATIENT_FACTS } from "@/demo/patients";
import { PATIENTS, startDemo } from "@/demo/session";
import { useRouter } from "@/i18n/navigation";
import { useT } from "@/theme/words";

/** The demo patients (design §13.1, Req 4.1–4.3): no sign-up, nothing sent, nothing stored. */
export function DemoPicker() {
  const t = useT();
  const router = useRouter();
  return (
    <>
      <PageTitle eyebrow={t("Demo.label")}>{t("Demo.title")}</PageTitle>
      <p>{t("Demo.intro")}</p>
      <p className="text-sm text-muted">{t("Demo.noList")}</p>
      <ul className="flex flex-col gap-3">
        {PATIENTS.map((p) => (
          <Card as="li" key={p}>
            <h2 className="text-xl font-semibold">
              {t(`Demo.patients.${p}.name`)}
            </h2>
            <p>{t(`Demo.patients.${p}.summary`)}</p>
            <p className="text-sm text-muted">
              {t("Demo.items", { count: PATIENT_FACTS[p].items })} ·{" "}
              {t(`Common.region.${PATIENT_FACTS[p].userRegion}`)}
            </p>
            <Button
              className="self-start"
              onClick={() => {
                startDemo(p);
                router.push("/medicines");
              }}
            >
              {t("Demo.open", { patient: t(`Demo.patients.${p}.name`) })}
            </Button>
          </Card>
        ))}
      </ul>
    </>
  );
}
