"use client";
/**
 * The four states of every data view (experience design §9): loading (a text label and
 * `aria-busy`), empty (a sentence and the next action), error (the mapped message and a retry
 * when the call is idempotent). Long content is the views' own concern (wrapping, show more).
 */
import type { ReactNode } from "react";

import { useT } from "@/theme/words";

import { LargeTitle } from "./cards";
import { Button } from "./ui";

export type ViewState = (
  | { state: "loading"; label?: string }
  | { state: "empty"; message: string; action?: ReactNode }
  | { state: "error"; messageKey: string; retry?: () => void }
) & {
  /**
   * The page's title, when the state replaces the whole page: shown as its one `h1`, so a
   * screen-reader user still lands on a heading (plan D2.5).
   */
  title?: ReactNode;
};

export function StateView({ title, ...props }: ViewState) {
  if (title === undefined) return <StateBody {...props} />;
  return (
    <>
      <LargeTitle title={title} />
      <StateBody {...props} />
    </>
  );
}

function StateBody(props: ViewState) {
  const t = useT();
  if (props.state === "loading")
    return (
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="card flex flex-col gap-3 p-4"
      >
        <p>{props.label ?? t("Common.loading")}</p>
        <div className="h-3 w-2/3 animate-pulse rounded-full bg-chip" />
        <div className="h-3 w-1/2 animate-pulse rounded-full bg-chip" />
      </div>
    );
  if (props.state === "empty")
    return (
      <div className="card flex flex-col items-start gap-3 p-4">
        <p>{props.message}</p>
        {props.action}
      </div>
    );
  return (
    <div role="alert" className="card flex flex-col items-start gap-3 p-4">
      <p>{t(props.messageKey)}</p>
      {props.retry ? (
        <Button variant="secondary" onClick={props.retry}>
          {t("Common.retry")}
        </Button>
      ) : null}
    </div>
  );
}
