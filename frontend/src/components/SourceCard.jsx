import { useState } from "react";
import { Check, Copy, ExternalLink, FileText } from "lucide-react";

export default function SourceCard({ source, index, onOpen, idPrefix, displayLocale }) {
  const [copied, setCopied] = useState(false);
  const pageNumber = source.page !== null && source.page !== undefined
    ? new Intl.NumberFormat(displayLocale, { useGrouping: false }).format(Number(source.page) + 1)
    : null;
  const citation = [
    source.filename || "Source document",
    source.scheme_name || null,
    pageNumber ? `Page ${pageNumber}` : null,
  ].filter(Boolean).join(" · ");

  async function copyCitation() {
    try {
      await navigator.clipboard.writeText(citation);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="source-card" id={`source-${idPrefix}-${index + 1}`}>
      <button
        className="source-card-main"
        onClick={() => onOpen?.(source)}
        aria-label={`View ${source.filename || "source document"} citation passage`}
      >
        <span className="source-number">{String(index + 1).padStart(2, "0")}</span>
        <span className="source-file-icon"><FileText size={17} /></span>
        <span className="source-info">
          <strong title={source.filename}>{source.filename || "Source document"}</strong>
          {source.scheme_name && <span>{source.scheme_name}</span>}
          <span>
            {source.page !== null && source.page !== undefined
              ? `Page ${pageNumber}`
              : "Page not provided"}
            {typeof source.score === "number" && ` · similarity ${new Intl.NumberFormat(displayLocale, { maximumFractionDigits: 2 }).format(source.score)}`}
          </span>
        </span>
        <FileText size={15} className="source-open-icon" />
      </button>
      {source.content && (
        <p className="source-excerpt">
          “{source.content.length > 240 ? `${source.content.slice(0, 240).trim()}…` : source.content}”
        </p>
      )}
      {source.source_url ? (
        <a className="source-official-link" href={source.source_url} target="_blank" rel="noreferrer">
          Open official document source <ExternalLink size={12} />
        </a>
      ) : (
        <span className="source-link-unavailable">Official source URL was not attached to this indexed document.</span>
      )}
      <button className="source-copy" onClick={copyCitation} aria-label={`Copy citation ${index + 1}`}>
        {copied ? <Check size={13} /> : <Copy size={13} />}
        {copied ? "Copied" : "Copy citation"}
      </button>
    </article>
  );
}
