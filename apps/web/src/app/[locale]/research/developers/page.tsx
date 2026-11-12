import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Developers } from "@/components/research/Developers";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/developers">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "developers");
}

export default function DevelopersPage() {
  return <Developers />;
}
