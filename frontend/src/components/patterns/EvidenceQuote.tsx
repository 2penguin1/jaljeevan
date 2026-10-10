import { ExternalLink } from "lucide-react";
import { cn, safeUrl, timeAgo } from "@/lib/format";

const SOURCE_LABEL: Record<string, string> = { gdelt: "News", rss: "News", reddit: "Reddit", x: "X", citizen: "Citizen" };

/** A verbatim quote from a post. Post text is untrusted: it is only ever rendered as text nodes. */
export function EvidenceQuote({ quote, title, summary, domain, source, credibility, url, publishedAt, place, weight, className }: {
  quote: string | null | undefined;
  title?: string;
  summary?: string | null;
  domain?: string | null;
  source: string;
  credibility?: number | null;
  url?: string | null;
  publishedAt?: string | null;
  place?: string | null;
  weight?: number;
  className?: string;
}) {
  const href = safeUrl(url);
  return (
    <figure className={cn("rounded-[6px] border hairline bg-surface p-4", className)}>
      <blockquote className="font-display text-[19px] leading-[1.35] text-text">
        &ldquo;{quote || title || summary}&rdquo;
      </blockquote>
      {summary && quote && <p className="mt-2 text-[13px] leading-relaxed text-text-2">{summary}</p>}
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-text-3">
        <span className="text-text-2">{domain || SOURCE_LABEL[source] || source}</span>
        {place && <span>{place}</span>}
        {publishedAt && <time dateTime={publishedAt}>{timeAgo(publishedAt)}</time>}
        {credibility != null && <span>Credibility <span className="num">{credibility.toFixed(1)}</span></span>}
        {weight != null && <span>Weight <span className="num">{weight.toFixed(2)}</span></span>}
        {href && (
          <a href={href} target="_blank" rel="noreferrer noopener" className="ml-auto inline-flex items-center gap-1 text-text-2 hover:text-text">
            Read source <ExternalLink size={12} aria-hidden />
          </a>
        )}
      </figcaption>
    </figure>
  );
}
