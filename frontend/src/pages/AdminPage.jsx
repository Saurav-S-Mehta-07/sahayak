import { useEffect, useState } from "react";
import { AlertCircle, Check, FilePlus2, RefreshCw, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";
import {
  fetchAdminDocuments,
  fetchAdminDiscoveries,
  fetchAdminEligibilityCriteria,
  fetchDocumentEvents,
  fetchSchemes,
  discoverAdminSchemes,
  ingestAdminDocument,
  updateAdminScheme,
  uploadAdminDocument,
  verifyAdminSchemeSource,
  verifyAdminDocument,
  createAdminEligibilityCriterion,
  reviewAdminDiscovery,
} from "../services/api.js";

export default function AdminPage() {
  const { signOut } = useAuth();
  const [schemes, setSchemes] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [discoveries, setDiscoveries] = useState([]);
  const [reviewNotes, setReviewNotes] = useState({});
  const [form, setForm] = useState({ scheme_id: "", source_url: "", language: "English", version_date: "" });
  const [file, setFile] = useState(null);
  const [events, setEvents] = useState({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const [availableSchemes, uploaded, discovered] = await Promise.all([
      fetchSchemes(),
      fetchAdminDocuments(),
      fetchAdminDiscoveries(),
    ]);
    setSchemes(availableSchemes);
    setDocuments(uploaded);
    setDiscoveries(discovered);
    setForm((current) => current.scheme_id
      ? current
      : { ...current, scheme_id: availableSchemes[0]?.id || "" });
  }

  async function runDiscovery() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await discoverAdminSchemes();
      setMessage(
        `Checked ${result.feeds_checked} configured feed(s); added ${result.new_discoveries} new review signal(s).`,
      );
      if (result.errors?.length) setError(result.errors.join(" "));
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function updateDiscovery(discovery, status) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await reviewAdminDiscovery(
        discovery.id,
        status,
        reviewNotes[discovery.id] || "",
      );
      setMessage(`Updated review status for "${discovery.title}".`);
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh().catch((cause) => setError(cause.message));
  }, []);

  function chooseScheme(id) {
    const selected = schemes.find((scheme) => scheme.id === id);
    setForm((current) => ({ ...current, scheme_id: id, source_url: selected?.official_source_url || "" }));
  }

  async function submitUpload(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF file first.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const body = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (value) body.append(key, value);
      });
      body.append("upload", file);
      const document = await uploadAdminDocument(body);
      setMessage(`Stored ${document.filename}. Verify its source before indexing.`);
      setFile(null);
      event.target.reset();
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action, id) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await action(id);
      setMessage(`${updated.filename}: ${updated.verification_status}; indexing ${updated.indexing_status}.`);
      await refresh();
    } catch (cause) {
      setError(cause.message);
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  async function showEvents(id) {
    try {
      const result = await fetchDocumentEvents(id);
      setEvents((current) => ({ ...current, [id]: result }));
    } catch (cause) {
      setError(cause.message);
    }
  }

  async function saveScheme(event, schemeId) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const changes = Object.fromEntries(formData.entries());
    setBusy(true);
    setError("");
    try {
      await updateAdminScheme(schemeId, changes);
      setMessage("Scheme metadata saved. Review the source again before using it.");
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmSchemeSource(schemeId) {
    setBusy(true);
    setError("");
    try {
      await verifyAdminSchemeSource(schemeId);
      setMessage("Source marked reviewed by an administrator.");
      await refresh();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  async function signOutNow() {
    setError("");
    try {
      await signOut();
    } catch (cause) {
      setError(cause.message);
    }
  }

  return (
    <main className="admin-page">
      <header className="catalog-header"><div><span className="eyebrow"><ShieldCheck size={14} /> ADMINISTRATION</span><h1>Document management</h1><p>Uploaded files remain unverified until reviewed. Only verified documents can be indexed into the existing RAG store.</p></div><div className="admin-header-actions"><button className="button button-secondary button-small" onClick={signOutNow}>Sign out</button><button className="icon-button" onClick={() => refresh().catch((cause) => setError(cause.message))} aria-label="Refresh document list"><RefreshCw size={17} /></button></div></header>
      {error && <div className="form-error" role="alert"><AlertCircle size={16} />{error}</div>}
      {message && <div className="form-success" role="status"><Check size={16} />{message}</div>}
      <section className="admin-panel">
        <div className="admin-panel-heading">
          <div>
            <h2>Discovered scheme signals</h2>
            <p>Configured official RSS feeds provide leads for human review only. A feed item is not proof of scheme details and is never indexed automatically.</p>
          </div>
          <button className="button button-small" disabled={busy} onClick={runDiscovery}>
            {busy ? "Checking…" : "Discover new schemes"}
          </button>
        </div>
        {discoveries.length === 0 ? (
          <p className="catalog-empty">No discovery signals yet. Configure official feeds before running discovery.</p>
        ) : (
          <div className="admin-doc-list">
            {discoveries.map((discovery) => (
              <article className="admin-doc" key={discovery.id}>
                <div className="admin-doc-main">
                  <div>
                    <h3>{discovery.title}</h3>
                    <p>{discovery.source_organization} · {discovery.published_at || "Publication date unavailable"} · discovered {discovery.discovered_at}</p>
                    {discovery.excerpt && <p>{discovery.excerpt}</p>}
                    <a href={discovery.source_url} target="_blank" rel="noreferrer">Open original official signal</a>
                  </div>
                  <span className="status-tag">{discovery.status.replaceAll("_", " ")}</span>
                </div>
                {discovery.status !== "rejected" && (
                  <>
                    <label className="discovery-review-notes">
                      Review notes
                      <textarea
                        rows={2}
                        maxLength={2000}
                        value={reviewNotes[discovery.id] ?? discovery.review_notes ?? ""}
                        onChange={(event) => setReviewNotes((current) => ({
                          ...current,
                          [discovery.id]: event.target.value,
                        }))}
                      />
                    </label>
                    <div className="admin-doc-actions">
                      {discovery.status !== "under_review" && <button className="button button-small" disabled={busy} onClick={() => updateDiscovery(discovery, "under_review")}>Mark under review</button>}
                      {discovery.status !== "needs_more_information" && <button className="button button-secondary button-small" disabled={busy} onClick={() => updateDiscovery(discovery, "needs_more_information")}>Request more information</button>}
                      <button className="button button-secondary button-small" disabled={busy} onClick={() => updateDiscovery(discovery, "rejected")}>Reject signal</button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="admin-panel">
        <div className="admin-panel-heading"><div><h2>Scheme source directory</h2><p>Review and correct the scheme record before confirming a portal link. This is an administrator review, not an external government verification.</p></div></div>
        <div className="admin-scheme-list">
          {schemes.map((scheme) => (
            <details className="admin-scheme" key={scheme.id}>
              <summary>{scheme.name}<span className={`status-tag ${scheme.source_status === "verified" ? "status-good" : ""}`}>{scheme.source_status.replaceAll("_", " ")}</span></summary>
              <form className="admin-upload-form" onSubmit={(event) => saveScheme(event, scheme.id)}>
                <label>Scheme name<input name="name" required maxLength={160} defaultValue={scheme.name} /></label>
                <label>Ministry<input name="ministry" required maxLength={160} defaultValue={scheme.ministry} /></label>
                <label>Source portal URL<input name="official_source_url" type="url" required defaultValue={scheme.official_source_url} /></label>
                <label>Language<input name="language" required maxLength={40} defaultValue={scheme.language} /></label>
                <label>Version date<input name="version_date" type="date" defaultValue={scheme.version_date || ""} /></label>
                <div className="admin-doc-actions">
                  <button className="button button-secondary button-small" disabled={busy}>Save metadata</button>
                  {scheme.source_status !== "verified" && <button className="button button-small" type="button" disabled={busy} onClick={() => confirmSchemeSource(scheme.id)}>Confirm source reviewed</button>}
                </div>
              </form>
            </details>
          ))}
        </div>
      </section>
      <section className="admin-panel">
        <div className="admin-panel-heading"><FilePlus2 size={18} /><div><h2>Add a scheme PDF</h2><p>Use a source URL matching the registered official source. File hash and page count are recorded.</p></div></div>
        <form className="admin-upload-form" onSubmit={submitUpload}>
          <label>Scheme<select required value={form.scheme_id} onChange={(event) => chooseScheme(event.target.value)}><option value="" disabled>Select scheme</option>{schemes.map((scheme) => <option value={scheme.id} disabled={scheme.source_status !== "verified"} key={scheme.id}>{scheme.name}{scheme.source_status !== "verified" ? " — review source first" : ""}</option>)}</select></label>
          <label>Official source URL<input type="url" required value={form.source_url} onChange={(event) => setForm({ ...form, source_url: event.target.value })} /></label>
          <div className="admin-form-row"><label>Document language<input required maxLength={40} value={form.language} onChange={(event) => setForm({ ...form, language: event.target.value })} /></label><label>Version date (optional)<input type="date" value={form.version_date} onChange={(event) => setForm({ ...form, version_date: event.target.value })} /></label></div>
          <label>PDF file<input type="file" accept="application/pdf,.pdf" required onChange={(event) => setFile(event.target.files?.[0] || null)} /><small>PDF only · maximum 40 MB</small></label>
          <button className="button" disabled={busy}>{busy ? "Processing…" : "Upload for review"}</button>
        </form>
      </section>

      <section className="admin-panel">
        <div className="admin-panel-heading"><div><h2>Document inventory</h2><p>{documents.length} uploaded document{documents.length === 1 ? "" : "s"}</p></div></div>
        {documents.length === 0 ? <p className="catalog-empty">No admin-managed PDFs uploaded. Existing indexed files have not been changed.</p> : (
          <div className="admin-doc-list">
            {documents.map((document) => (
              <article className="admin-doc" key={document.id}>
                <div className="admin-doc-main"><div><h3>{document.filename}</h3><p>{document.scheme_name} · {document.page_count ?? "?"} pages · {document.language} · SHA-256 {document.sha256.slice(0, 12)}…</p><a href={document.source_url} target="_blank" rel="noreferrer">Review source</a></div><div className="admin-statuses"><span className={`status-tag ${document.verification_status === "verified" ? "status-good" : ""}`}>{document.verification_status.replaceAll("_", " ")}</span><span className="status-tag">{document.extraction_status} · {document.indexing_status}</span></div></div>
                <div className="admin-doc-actions">
                  {document.verification_status !== "verified" && <button className="button button-small" disabled={busy} onClick={() => runAction(verifyAdminDocument, document.id)}>Confirm source</button>}
                  {document.verification_status === "verified" && document.indexing_status !== "indexed" && <button className="button button-small" disabled={busy} onClick={() => runAction(ingestAdminDocument, document.id)}>{document.indexing_status === "failed" ? "Retry indexing" : "Index document"}</button>}
                  <button className="button button-secondary button-small" onClick={() => showEvents(document.id)}>Processing log</button>
                </div>
                {document.verification_status === "verified" && document.indexing_status === "indexed" && (
                  <EligibilityCriterionForm
                    document={document}
                    onError={setError}
                    onSaved={(criterion) => setMessage(`Added reviewed ${criterion.field_key} criterion for ${document.scheme_name}.`)}
                  />
                )}
                {events[document.id] && <ol className="admin-events">{events[document.id].map((event, index) => <li key={`${event.created_at}-${index}`}><time>{event.created_at}</time> <strong>{event.event}</strong> — {event.detail}</li>)}</ol>}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function EligibilityCriterionForm({ document, onError, onSaved }) {
  const [criteria, setCriteria] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    fetchAdminEligibilityCriteria(document.scheme_id)
      .then((items) => {
        if (active) setCriteria(items);
      })
      .catch((cause) => {
        if (active) onError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [document.scheme_id, onError]);

  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const operator = values.get("operator");
    const rawValue = String(values.get("expected_value") || "").trim();
    if (!rawValue) {
      onError("Enter an expected value for this criterion.");
      return;
    }
    let expectedValue = rawValue;
    if (operator === "gte" || operator === "lte") {
      expectedValue = Number(rawValue);
      if (!Number.isFinite(expectedValue)) {
        onError("Numeric criteria require a numeric expected value.");
        return;
      }
    } else if (operator === "in") {
      expectedValue = rawValue.split(",").map((value) => value.trim()).filter(Boolean);
    }

    setBusy(true);
    onError("");
    try {
      const criterion = await createAdminEligibilityCriterion(document.scheme_id, {
        field_key: values.get("field_key"),
        operator,
        expected_value: expectedValue,
        description: values.get("description"),
        source_document_id: document.id,
        source_page: Number(values.get("source_page")),
        source_excerpt: values.get("source_excerpt"),
      });
      setCriteria((current) => [...current, criterion]);
      onSaved(criterion);
      form.reset();
    } catch (cause) {
      onError(cause.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="admin-criteria">
      <summary>Eligibility criteria ({criteria.length})</summary>
      {criteria.map((criterion) => (
        <p key={criterion.id}>
          <strong>{criterion.field_key}</strong> {criterion.operator} {JSON.stringify(criterion.expected_value)}
          {" — "}{criterion.filename}, page {criterion.source_page}
        </p>
      ))}
      <form className="admin-upload-form" onSubmit={submit}>
        <label>Profile field key<input name="field_key" required maxLength={64} placeholder="age, state, occupation" /></label>
        <div className="admin-form-row">
          <label>Condition<select name="operator"><option value="eq">equals</option><option value="ne">does not equal</option><option value="gte">at least</option><option value="lte">at most</option><option value="in">is one of</option><option value="contains">contains</option></select></label>
          <label>Expected value<input name="expected_value" required maxLength={200} placeholder="For “is one of”, separate values with commas" /></label>
        </div>
        <label>Criterion description<input name="description" required maxLength={300} /></label>
        <label>PDF page number<input name="source_page" type="number" min="1" max={document.page_count || undefined} required defaultValue="1" /></label>
        <label>Exact supporting excerpt<textarea name="source_excerpt" required minLength={12} maxLength={2000} rows={3} /><small>Must match text on this page of the verified PDF.</small></label>
        <button className="button button-secondary button-small" disabled={busy}>{busy ? "Saving…" : "Add reviewed criterion"}</button>
      </form>
    </details>
  );
}
