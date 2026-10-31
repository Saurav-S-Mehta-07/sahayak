import { useEffect, useMemo, useState } from "react";
import { AlertCircle, FileText, RefreshCw, Search, X } from "lucide-react";
import { fetchDocuments } from "../services/api.js";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selected) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selected]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setDocuments(await fetchDocuments());
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () => documents.filter((document) => document.filename.toLowerCase().includes(query.trim().toLowerCase())),
    [documents, query],
  );

  return (
    <section className="documents-page">
      <div className="documents-heading">
        <div>
          <span className="eyebrow"><span className="eyebrow-dot" /> KNOW YOUR SOURCES</span>
          <h1>Explore documents</h1>
          <p>Browse the PDF sources currently indexed by the assistant.</p>
        </div>
        <button className="secondary-button" onClick={load} disabled={loading}>
          <RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh
        </button>
      </div>

      <div className="documents-toolbar">
        <Search size={17} />
        <label className="sr-only" htmlFor="document-search">Search documents</label>
        <input id="document-search" placeholder="Search by document name..." value={query} onChange={(event) => setQuery(event.target.value)} />
        {query && <button className="icon-button" onClick={() => setQuery("")} aria-label="Clear search"><X size={15} /></button>}
        <span className="document-total">{loading ? "…" : `${filtered.length} ${filtered.length === 1 ? "document" : "documents"}`}</span>
      </div>

      {error ? (
        <div className="documents-state error-state">
          <AlertCircle size={22} />
          <strong>Couldn’t load the document library</strong>
          <span>{error}</span>
          <button className="secondary-button" onClick={load}>Try again</button>
        </div>
      ) : loading ? (
        <div className="document-grid" aria-label="Loading documents">
          {[0, 1, 2].map((item) => <div className="document-skeleton" key={item} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="documents-state">
          <span className="empty-file-icon"><FileText size={23} /></span>
          <strong>{query ? "No matching documents" : "No documents indexed yet"}</strong>
          <span>{query ? "Try a different file name." : "The backend did not return any PDF sources from its vector store."}</span>
        </div>
      ) : (
        <div className="document-grid">
          {filtered.map((document) => (
            <button className="document-tile" key={`${document.filename}-${document.source}`} onClick={() => setSelected(document)}>
              <span className="document-icon"><FileText size={19} /></span>
              <span className="document-title">{document.filename}</span>
              <span className="document-stats">
                {document.page_count != null && `${document.page_count} pages`}
                {document.page_count != null && document.chunk_count != null && " · "}
                {document.chunk_count != null && `${document.chunk_count} indexed chunks`}
              </span>
              <span className="document-open-label">View metadata <span>↗</span></span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="source-modal-scrim" role="presentation" onClick={() => setSelected(null)}>
          <section className="source-detail-modal" role="dialog" aria-modal="true" aria-labelledby="document-detail-title" onClick={(event) => event.stopPropagation()}>
            <button className="icon-button source-modal-close" onClick={() => setSelected(null)} aria-label="Close document details"><X size={18} /></button>
            <span className="eyebrow">INDEXED DOCUMENT</span>
            <h2 id="document-detail-title">{selected.filename}</h2>
            <dl className="metadata-list">
              <div><dt>Indexed source</dt><dd>{selected.source}</dd></div>
              {selected.page_count != null && <div><dt>Pages</dt><dd>{selected.page_count}</dd></div>}
              {selected.chunk_count != null && <div><dt>Indexed chunks</dt><dd>{selected.chunk_count}</dd></div>}
            </dl>
          </section>
        </div>
      )}
    </section>
  );
}
