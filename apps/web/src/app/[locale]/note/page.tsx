import { noIndex } from "@/seo/metadata";
import { NotePage } from "@/components/note/NotePage";

export const metadata = noIndex;

export default function Note() {
  return <NotePage />;
}
