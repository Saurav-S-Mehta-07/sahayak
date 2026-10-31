import { useEffect, useState } from "react";
import { ArrowRight, Info } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  evaluateEligibility,
  fetchSchemes,
  recommendSchemes,
} from "../services/api.js";

export default function EligibilityPage() {
  const [profile, setProfile] = useState({ state: "", age: "", occupation: "", situation: "" });
  const [schemes, setSchemes] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [evaluation, setEvaluation] = useState(null);
  const [recommendationError, setRecommendationError] = useState("");
  const [checking, setChecking] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.state?.schemeId) {
      setProfile((current) => ({ ...current, schemeId: location.state.schemeId }));
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  useEffect(() => {
    let active = true;
    fetchSchemes()
      .then((availableSchemes) => {
        if (active) setSchemes(availableSchemes);
      })
      .catch((error) => {
        if (active) setRecommendationError(error.message);
      });
    return () => {
      active = false;
    };
  }, []);

  async function checkDocumentedMatches() {
    setChecking(true);
    setRecommendationError("");
    const answers = {};
    if (/^\d{1,3}$/.test(profile.age.trim())) answers.age = Number(profile.age);
    if (profile.state.trim()) answers.state = profile.state.trim();
    if (profile.occupation.trim()) answers.occupation = profile.occupation.trim();
    try {
      if (profile.schemeId) {
        setEvaluation(await evaluateEligibility(profile.schemeId, answers));
        setRecommendations(null);
      } else {
        setRecommendations(await recommendSchemes(answers));
        setEvaluation(null);
      }
    } catch (error) {
      setRecommendationError(error.message);
    } finally {
      setChecking(false);
    }
  }

  function continueToChat(event) {
    event.preventDefault();
    const details = [
      profile.age && `Age: ${profile.age}`,
      profile.state && `State/UT: ${profile.state}`,
      profile.occupation && `Work or occupation: ${profile.occupation}`,
      profile.situation && `What I need help with: ${profile.situation}`,
    ].filter(Boolean).join("; ");
    const prompt = `Help me explore government schemes that may be relevant to my situation (${details || "I have not shared personal details yet"}). Use only available source documents, cite them, state what cannot be confirmed, and ask me for missing details. Do not decide or guarantee my eligibility.`;
    navigate("/chat", { state: { prefill: prompt } });
  }

  return (
    <main className="catalog-page eligibility-page">
      <header className="catalog-header"><div><span className="eyebrow">PERSONALIZED GUIDANCE</span><h1>Start with your situation</h1><p>Share only what you’re comfortable sharing. We’ll use your details to frame a question, not to make an official eligibility decision.</p></div></header>
      <form className="eligibility-form" onSubmit={continueToChat}>
        <label>Scheme, if you have one in mind
          <select value={profile.schemeId || ""} onChange={(event) => setProfile({ ...profile, schemeId: event.target.value })}>
            <option value="">All schemes with reviewed criteria</option>
            {schemes.map((scheme) => <option key={scheme.id} value={scheme.id}>{scheme.name}</option>)}
          </select>
        </label>
        <label>State or Union Territory<input maxLength={80} value={profile.state} onChange={(event) => setProfile({ ...profile, state: event.target.value })} placeholder="For example, Assam" /></label>
        <label>Age range<input maxLength={30} value={profile.age} onChange={(event) => setProfile({ ...profile, age: event.target.value })} placeholder="For example, 18–25" /></label>
        <label>Work or occupation<input maxLength={100} value={profile.occupation} onChange={(event) => setProfile({ ...profile, occupation: event.target.value })} placeholder="For example, student or farmer" /></label>
        <label>What would you like help with?<textarea maxLength={500} rows={4} value={profile.situation} onChange={(event) => setProfile({ ...profile, situation: event.target.value })} placeholder="Tell us what kind of support you’re looking for" /></label>
        <div className="eligibility-note"><Info size={17} /><span>Eligibility checks send these answers for this request only; they are not saved as a profile. Continuing to chat will include the selected details in your conversation. Don’t include Aadhaar, bank details, or other sensitive identifiers.</span></div>
        <button className="button button-secondary" type="button" disabled={checking} onClick={checkDocumentedMatches}>
          {checking ? "Checking reviewed criteria…" : "Find evidence-based matches"}
        </button>
        {recommendationError && <p className="form-error" role="alert">{recommendationError}</p>}
        {evaluation && (
          <section className="eligibility-results" aria-live="polite">
            <h2>{evaluation.scheme_name}: {evaluation.status.replaceAll("_", " ")}</h2>
            <p>{evaluation.message}</p>
            {evaluation.criteria.map((criterion, index) => (
              <article key={`${criterion.field}-${index}`}>
                <h3>{criterion.description}</h3>
                <p>Status: {criterion.status.replaceAll("_", " ")}</p>
                <blockquote>{criterion.source.excerpt}</blockquote>
                <small>{criterion.source.filename}, page {criterion.source.page} · <a href={criterion.source.url} target="_blank" rel="noreferrer">official source</a></small>
              </article>
            ))}
          </section>
        )}
        {recommendations && (
          <section className="eligibility-results" aria-live="polite">
            <p>{recommendations.message}</p>
            {recommendations.recommendations.length ? (
              recommendations.recommendations.map((match) => (
                <article key={match.scheme_id}>
                  <h2>{match.scheme_name}</h2>
                  {match.criteria.map((criterion, index) => (
                    <p key={`${criterion.field}-${index}`}>
                      {criterion.description} — {criterion.source.filename}, page {criterion.source.page}
                    </p>
                  ))}
                  <small>{match.message}</small>
                </article>
              ))
            ) : (
              <p>No evidence-backed matches can be confirmed from the reviewed criteria currently available. You can still ask a question in chat.</p>
            )}
          </section>
        )}
        <button className="button">Continue to chat <ArrowRight size={16} /></button>
      </form>
      <p className="catalog-footnote">For current eligibility decisions, confirm requirements with the official scheme authority. <Link to="/schemes">Browse official sources</Link>.</p>
    </main>
  );
}
