/** Why the home scenes run still (DP46): reduced motion, Save-Data or a 2G connection. */
type Connection = { saveData?: boolean; effectiveType?: string };

export function stillReason(): string | null {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return "reduce";
  const c = (navigator as Navigator & { connection?: Connection }).connection;
  if (c?.saveData) return "save-data";
  if (c?.effectiveType && /(^|-)2g$/.test(c.effectiveType)) return "slow";
  return null;
}
