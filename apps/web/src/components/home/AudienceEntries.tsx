/**
 * The two ways in (plan D1): patients and families, researchers and clinicians. Plain links on the
 * design tokens, no image and no script, so the home's first paint does not change.
 */
import { ArrowRightIcon } from "@/components/icons";
import { Link } from "@/i18n/navigation";
import { useT } from "@/theme/words";

const ENTRIES = [
  { key: "patients", href: "/scan" },
  { key: "researchers", href: "/research" },
] as const;

export function AudienceEntries() {
  const t = useT();
  return (
    <nav
      aria-labelledby="audience-title"
      data-testid="audience-entries"
      className="flex flex-col gap-3"
    >
      <h2 id="audience-title" className="sr-only">
        {t("Home.audience.title")}
      </h2>
      <ul className="grid gap-4 md:grid-cols-2">
        {ENTRIES.map(({ key, href }) => (
          <li key={key} className="flex">
            <Link
              href={href}
              data-testid={`audience-${key}`}
              className="card flex w-full flex-col gap-2 p-5 no-underline hover:bg-chip"
            >
              <span className="text-xl leading-snug font-semibold">
                {t(`Home.audience.${key}.title`)}
              </span>
              <span className="text-muted">
                {t(`Home.audience.${key}.body`)}
              </span>
              <span className="mt-auto inline-flex items-center gap-1 pt-1 font-bold text-accent">
                {t(`Home.audience.${key}.cta`)}
                <ArrowRightIcon size={18} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
