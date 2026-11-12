import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { PassportList } from "@/passport/screens/PassportList";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/passport">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "passport");
}

export default function PassportPage() {
  return <PassportList />;
}
