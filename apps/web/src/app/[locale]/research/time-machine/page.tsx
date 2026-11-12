import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { TimeMachine } from "@/components/timemachine/TimeMachine";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/time-machine">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "timeMachine");
}

export default function TimeMachinePage() {
  return <TimeMachine />;
}
