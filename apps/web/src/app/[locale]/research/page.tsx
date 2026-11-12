import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Research } from "@/components/research/Research";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "research");
}

export default function ResearchPage() {
  return <Research />;
}
