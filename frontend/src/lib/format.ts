import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

const grouped = new Intl.NumberFormat("en-IN");
const oneDecimal = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

/** People counts the way Indian readers say them: 12,000 / 39.8 lakh / 2.5 crore. */
export function formatPeople(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1e7) return `${oneDecimal.format(n / 1e7)} crore`;
  if (n >= 1e5) return `${oneDecimal.format(n / 1e5)} lakh`;
  return grouped.format(n);
}

export const formatInt = (n: number | null | undefined) => (n === null || n === undefined ? "—" : grouped.format(n));

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const seconds = (new Date(iso).getTime() - now) / 1000;
  for (const [unit, size] of STEPS) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

/** Only http(s) links from untrusted posts are rendered as links. */
export const safeUrl = (url: string | null | undefined) => (url && /^https?:\/\//i.test(url) ? url : undefined);
