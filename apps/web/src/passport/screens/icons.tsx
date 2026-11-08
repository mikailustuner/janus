/**
 * Status and comparison shapes (design §8, Req 10.4): each status has its own shape, so meaning
 * never rests on colour; the text next to the icon carries it (icons are `aria-hidden`).
 * Lucide shapes, 1.9 px stroke, as `components/icons.tsx`.
 */
import type { ReactNode } from "react";

import type { CmpResult, Status } from "../model";

function Svg({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
      className="mt-0.5 shrink-0"
    >
      {children}
    </svg>
  );
}

const STATUS: Record<Status, ReactNode> = {
  present: <path d="M20 6 9 17l-5-5" />,
  not_present: <path d="M5 12h14" />,
  not_in_source: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m5.6 5.6 12.8 12.8" />
    </>
  ),
  source_unavailable: (
    <>
      <path d="M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 0 1 2.4 8.3" />
      <path d="m2 2 20 20" />
    </>
  ),
};
const RESULT: Record<CmpResult, ReactNode> = {
  matched: <path d="M20 6 9 17l-5-5" />,
  differs: (
    <>
      <path d="M5 9h14M5 15h14" />
      <path d="m15 4-6 16" />
    </>
  ),
  could_not_compare: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01" />
    </>
  ),
};

export const StatusIcon = ({ status }: { status: Status }) => (
  <Svg>{STATUS[status]}</Svg>
);
export const ResultIcon = ({ result }: { result: CmpResult }) => (
  <Svg size={18}>{RESULT[result]}</Svg>
);
export const CopyIcon = () => (
  <Svg size={18}>
    <rect x="8" y="8" width="13" height="13" rx="2" />
    <path d="M4 16V5a1 1 0 0 1 1-1h11" />
  </Svg>
);
