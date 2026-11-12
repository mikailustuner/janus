import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Simulate } from "@/components/simulation/Simulate";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/simulate">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "simulate");
}

export default function SimulatePage() {
  return <Simulate />;
}
