/** Locale formatting of months, dates and numbers returned as numbers (Req 2.3, DP28). */
export function formatMonth(month: string, locale: string): string {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(Date.UTC(y, m - 1, 1));
}

export function formatDate(date: string, locale: string): string {
  const [y, m, d] = date.slice(0, 10).split("-").map(Number) as [
    number,
    number,
    number,
  ];
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(Date.UTC(y, m - 1, d));
}

/** A ratio or bound: two significant decimals below 10, one below 100, none above. */
export function formatRatio(x: number, locale: string): string {
  const digits = x < 10 ? 2 : x < 100 ? 1 : 0;
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(x);
}

export function formatCount(n: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(n);
}

export function formatShare(share: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(share);
}
