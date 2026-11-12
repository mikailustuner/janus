import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { ForResearchers } from "@/components/research/ForResearchers";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/for-researchers">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "forResearchers");
}

export default function ForResearchersPage() {
  return <ForResearchers />;
}
