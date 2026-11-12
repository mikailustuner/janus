import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Seance } from "@/components/seance/Seance";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/seance">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "seance");
}

export default function SeancePage() {
  return <Seance />;
}
