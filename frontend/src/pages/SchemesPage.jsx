import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchSchemes } from "../services/api.js";

export default function SchemesPage() {
  const [schemes, setSchemes] = useState([]);
  const [query, setQuery] = useState("");
  const [ministry, setMinistry] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSchemes().then(setSchemes).catch((cause) => setError(cause.message));
  }, []);

  const ministries = useMemo(
    () => [...new Set(schemes.map((scheme) => scheme.ministry))].sort(),
    [schemes],
  );
  const shown = schemes.filter((scheme) =>
    `${scheme.name} ${scheme.ministry}`.toLowerCase().includes(query.toLowerCase())
    && (!ministry || scheme.ministry === ministry),
  );

  return (
    <main className="catalog-page">
      <header className="catalog-header"><div><span className="eyebrow">SCHEME DIRECTORY</span><h1>Explore schemes</h1><p>Browse official scheme portals. A source link is not a claim that its PDF is indexed in this assistant.</p></div><Link to="/eligibility" className="button button-secondary">Get guidance</Link></header>
      <div className="scheme-filters">
        <label className="catalog-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by scheme or ministry" aria-label="Search scheme catalog" /></label>
        <label className="scheme-ministry-filter"><span className="sr-only">Filter by ministry</span><select value={ministry} onChange={(event) => setMinistry(event.target.value)}><option value="">All ministries</option>{ministries.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {!schemes.length && !error && <p className="catalog-empty">Loading scheme sources…</p>}
      <section className="scheme-grid">
        {shown.map((scheme) => (
          <article className="scheme-card" key={scheme.id}>
            <div className="scheme-card-top"><span className="scheme-icon"><Search size={17} /></span><span className="status-tag">{scheme.indexed_verified_count ? "Verified document indexed" : "PDF not yet verified"}</span></div>
            <h2>{scheme.name}</h2><p>{scheme.ministry}</p>
            <div className="scheme-card-foot"><a href={scheme.official_source_url} target="_blank" rel="noreferrer">Source portal <ArrowUpRight size={14} /></a><span>{scheme.indexed_verified_count ? "Verified PDF indexed" : "No verified PDF indexed"}</span></div>
            <details className="scheme-details">
              <summary>Scheme details</summary>
              <dl>
                <div><dt>Ministry</dt><dd>{scheme.ministry}</dd></div>
                <div><dt>Language/version</dt><dd>{scheme.language || "Not recorded"}{scheme.version_date ? ` · ${scheme.version_date}` : ""}</dd></div>
                <div><dt>Benefits, eligibility, documents and application steps</dt><dd>Not documented in this directory. Check the linked official portal; ask the assistant only if a verified source document is available.</dd></div>
              </dl>
              <Link
                className="scheme-chat-link"
                to="/chat"
                state={{ prefill: `I want to understand ${scheme.name}. Use retrieved documents only, cite each factual claim, and tell me clearly if no verified source passage is available.` }}
              >
                Continue about this scheme in chat
              </Link>
              <Link className="scheme-chat-link" to="/eligibility" state={{ schemeId: scheme.id }}>
                Check documented eligibility
              </Link>
            </details>
          </article>
        ))}
      </section>
      {schemes.length > 0 && shown.length === 0 && <p className="catalog-empty">No schemes match that search.</p>}
      <aside className="catalog-note"><strong>Before you apply</strong><span>Scheme rules can change. Check the linked official portal for current terms. This directory is informational, not an eligibility decision.</span></aside>
    </main>
  );
}
