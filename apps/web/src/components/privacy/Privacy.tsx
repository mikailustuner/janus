"use client";
/**
 * The privacy page (design §12, Req 21): what stays on the device, what is sent, what is stored
 * and where (the region from `GET /privacy/storage`, never guessed), how long, how to delete, how
 * shared numbers are protected and the limits, the legal frame without any compliance claim, and
 * the data sources.
 */
import { StateView } from "@/components/StateView";
import { Card, PageTitle, SectionTitle } from "@/components/ui";
import { useSession } from "@/flow/janus";
import { useCall } from "@/flow/useCall";
import { Link } from "@/i18n/navigation";
import { useT } from "@/theme/words";

const SECTIONS = [
  "device",
  "sent",
  "stored",
  "where",
  "howLong",
  "delete",
  "protection",
  "legal",
  "network",
  "sources",
] as const;

export function Privacy() {
  const t = useT();
  const session = useSession();
  const storage = useCall(
    session.client ? () => session.client!.privacyStorage() : null,
    [session.client],
  );
  return (
    <>
      <PageTitle>{t("Privacy.title")}</PageTitle>
      <p>{t("Privacy.intro")}</p>
      {SECTIONS.map((s) => (
        <Card key={s} aria-labelledby={`privacy-${s}`}>
          <SectionTitle id={`privacy-${s}`}>
            {t(`Privacy.${s}.title`)}
          </SectionTitle>
          {s === "where" ? (
            storage.status === "loading" ? (
              <StateView state="loading" />
            ) : storage.status === "ok" ? (
              <p data-testid="storage-region">
                {storage.data.donations_enabled &&
                storage.data.donation_storage_region
                  ? t("Privacy.where.region", {
                      region: storage.data.donation_storage_region,
                      eu: storage.data.in_eu ? t("Privacy.where.inEu") : "",
                    })
                  : t("Privacy.where.disabled")}
              </p>
            ) : (
              <p data-testid="storage-region">{t("Privacy.where.unknown")}</p>
            )
          ) : (
            <p>{t(`Privacy.${s}.body`)}</p>
          )}
          {s === "protection" ? <p>{t("Privacy.protection.limits")}</p> : null}
          {s === "delete" ? (
            <ul className="flex flex-wrap gap-x-3">
              <li>
                <Link
                  href="/donate/delete"
                  className="inline-flex min-h-11 items-center underline underline-offset-4"
                >
                  {t("Donate.delete.title")}
                </Link>
              </li>
              <li>
                <Link
                  href="/note/withdraw"
                  className="inline-flex min-h-11 items-center underline underline-offset-4"
                >
                  {t("Withdraw.title")}
                </Link>
              </li>
              <li>
                <Link
                  href="/settings"
                  className="inline-flex min-h-11 items-center underline underline-offset-4"
                >
                  {t("Settings.deleteTitle")}
                </Link>
              </li>
            </ul>
          ) : null}
        </Card>
      ))}
    </>
  );
}
