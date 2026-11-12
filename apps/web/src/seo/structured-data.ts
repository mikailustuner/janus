/**
 * Schema.org data for the home page: a WebSite and a WebApplication. Deliberately no
 * MedicalWebPage or any other type that asserts medical review: Janus is a research prototype
 * and expert review has not yet been done. "ReferenceApplication" makes no medical claim.
 */
import { SITE_URL } from "@/seo/routes";

const REPO = "https://github.com/mikailustuner/janus";
const LICENSE = "https://www.apache.org/licenses/LICENSE-2.0";

export function structuredData(input: {
  locale: string;
  name: string;
  description: string;
}) {
  const url = `${SITE_URL}/${input.locale}`;
  return [
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      name: input.name,
      url,
      inLanguage: input.locale,
    },
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "@id": `${SITE_URL}/#app`,
      name: input.name,
      description: input.description,
      url,
      inLanguage: input.locale,
      applicationCategory: "ReferenceApplication",
      operatingSystem: "Any (web browser)",
      browserRequirements: "Requires JavaScript",
      isAccessibleForFree: true,
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
      license: LICENSE,
      isBasedOn: {
        "@type": "SoftwareSourceCode",
        codeRepository: REPO,
        license: LICENSE,
        programmingLanguage: "TypeScript",
      },
      author: { "@type": "Person", name: "Mikail Üstüner" },
    },
  ];
}

/** JSON for an inline script: `<` is escaped so the data can never close the tag. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
