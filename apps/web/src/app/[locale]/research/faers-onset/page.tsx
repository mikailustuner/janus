import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { OnsetTable } from "@/components/research/OnsetTable";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/faers-onset">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "faersOnset");
}

export default function FaersOnsetPage() {
  return <OnsetTable />;
}
