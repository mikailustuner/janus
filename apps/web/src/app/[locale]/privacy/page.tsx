import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Privacy } from "@/components/privacy/Privacy";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/privacy">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "privacy");
}

export default function Page() {
  return <Privacy />;
}
