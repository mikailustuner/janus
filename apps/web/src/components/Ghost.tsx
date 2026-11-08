/**
 * The ghost of a finding (Night Pharmacy; steering design.md "Ghost"): a soft glowing mist body
 * with a teal edge, two eyes and a wavy tail, drawn in code. Used on the home scenes and on the
 * findings (Night Pharmacy). Motion is CSS only (`.ghost-*` in theme/home-scenes.css): an idle float, the tail wave
 * and an occasional blink; `--lean` (deg) lets a parent tilt it toward the pointer. Every motion
 * stops under `prefers-reduced-motion`. The shape is decorative: the meaning is carried by the
 * text next to it, so it is always `aria-hidden`.
 */
import { useId } from "react";

export function Ghost({
  size = 34,
  animated = false,
  className = "",
}: {
  size?: number;
  animated?: boolean;
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  return (
    <svg
      viewBox="0 0 64 80"
      width={size}
      height={(size * 80) / 64}
      className={`ghost ${animated ? "ghost-animated" : ""} ${className}`}
      aria-hidden
      focusable="false"
    >
      <defs>
        <radialGradient id={`gb${id}`} cx="50%" cy="38%" r="62%">
          <stop offset="0%" stopColor="var(--ghost-core)" stopOpacity="0.98" />
          <stop offset="70%" stopColor="var(--ghost-core)" stopOpacity="0.82" />
          <stop
            offset="100%"
            stopColor="var(--ghost-edge)"
            stopOpacity="0.55"
          />
        </radialGradient>
        <filter id={`gg${id}`} x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g className="ghost-body" filter={`url(#gg${id})`}>
        {/* Head and body; the tail is a separate path so it can wave. */}
        <path
          d="M32 6C18 6 9 17 9 31v22c0 4 3 6 6 6h34c3 0 6-2 6-6V31C55 17 46 6 32 6Z"
          fill={`url(#gb${id})`}
          stroke="var(--ghost-edge)"
          strokeWidth="1.6"
        />
        <path
          className="ghost-tail"
          d="M9 52c4 10 9 14 13 9 3 7 8 10 11 4 3 8 9 9 12 1 4 5 9 1 10-14"
          fill={`url(#gb${id})`}
          stroke="var(--ghost-edge)"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <g className="ghost-eyes" fill="var(--ghost-eye)">
          <ellipse cx="24" cy="30" rx="3.6" ry="4.6" />
          <ellipse cx="40" cy="30" rx="3.6" ry="4.6" />
        </g>
      </g>
    </svg>
  );
}
