"use client";
/** "Do not stop this medicine suddenly." in the interface language (medical-safety rule 4, Req 14.5). */
import { sentence, type Loaded } from "@/vocabulary";

import { AlertIcon } from "./icons";

export function AbruptStopLine({ vocab }: { vocab: Loaded }) {
  return (
    <p
      className="flex items-start gap-2 font-bold text-warn"
      data-testid="abrupt-stop"
    >
      <AlertIcon size={20} className="mt-0.5 shrink-0" />
      <span>{sentence(vocab, "abrupt_stop")}</span>
    </p>
  );
}
