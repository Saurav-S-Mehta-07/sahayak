import { ArrowRight, BookOpenText, CheckCircle2, FileCheck2, Languages, MessageCircle, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

const questions = [
  "What documents are needed to apply?",
  "Can you explain this scheme in simple language?",
  "Where can I check the official application process?",
];

export default function HomePage() {
  return (
    <main className="public-page">
      <header className="public-nav">
        <Link className="public-brand" to="/"><span className="brand-mark"><ShieldCheck size={19} /></span>Yojana Sahayak</Link>
        <nav aria-label="Public navigation">
          <Link to="/schemes">Explore schemes</Link>
          <a href="#how-it-works">How it works</a>
          <Link to="/login" className="public-login">Log in</Link>
          <Link to="/register" className="button button-small">Create account</Link>
        </nav>
      </header>

      <section className="landing-hero">
        <div className="hero-copy">
          <span className="eyebrow"><span className="eyebrow-dot" /> A clearer way to understand public schemes</span>
          <h1>Government schemes,<br /><span>made easier to understand.</span></h1>
          <p>Ask questions, explore scheme information, and get answers grounded in available source documents. If we cannot find supporting evidence, we’ll say so.</p>
          <div className="hero-actions">
            <Link to="/schemes" className="button">Explore schemes <ArrowRight size={16} /></Link>
            <Link to="/eligibility" className="button button-secondary">Check what may fit</Link>
          </div>
          <div className="hero-assurance"><ShieldCheck size={16} /><span>Source-backed answers. Clear about what is and isn’t verified.</span></div>
        </div>
        <div className="hero-example" aria-label="Example questions">
          <div className="example-top"><span className="example-status" /> ASK YOJANA SAHAYAK <span className="example-label">EXAMPLE</span></div>
          <div className="example-prompt"><MessageCircle size={16} /> How can I understand a scheme’s requirements?</div>
          <div className="example-rule" />
          {questions.map((question) => <div className="example-question" key={question}><ArrowRight size={14} />{question}</div>)}
          <p className="example-note">Answers depend on the documents currently available in the library.</p>
        </div>
      </section>

      <section className="trust-strip" aria-label="Product principles">
        <div><FileCheck2 /><span><strong>Evidence first</strong><small>Sources shown with retrieved answers</small></span></div>
        <div><CheckCircle2 /><span><strong>No confident guessing</strong><small>Missing evidence is stated clearly</small></span></div>
        <div><Languages /><span><strong>Language choices</strong><small>Response-language options and heuristic detection; quality varies by source and is not certified</small></span></div>
      </section>

      <section className="landing-section" id="how-it-works">
        <div className="section-heading"><span className="eyebrow">HOW IT WORKS</span><h2>Start with a question.<br />Stay close to the source.</h2></div>
        <div className="step-grid">
          <article><span>01</span><BookOpenText /><h3>Explore</h3><p>Browse a scheme catalog with links to official programme sources.</p></article>
          <article><span>02</span><MessageCircle /><h3>Ask in context</h3><p>Continue the conversation naturally. Your account keeps your own conversation history.</p></article>
          <article><span>03</span><ShieldCheck /><h3>Review evidence</h3><p>Open the cited passages and check the document and page before acting.</p></article>
        </div>
      </section>

      <section className="landing-cta">
        <div><span className="eyebrow">A PRACTICAL FIRST STEP</span><h2>Find the information you need,<br />without the guesswork.</h2></div>
        <div className="hero-actions"><Link to="/register" className="button">Create a free account <ArrowRight size={16} /></Link><Link to="/schemes" className="text-link">Browse scheme sources</Link></div>
      </section>

      <section className="landing-section faq-section">
        <div className="section-heading"><span className="eyebrow">TRANSPARENCY</span><h2>Good to know</h2></div>
        <details><summary>Are all scheme documents already available here?</summary><p>No. The catalog links to scheme source portals; the document library may not yet contain a verified PDF for every scheme.</p></details>
        <details><summary>Does an answer confirm that I am eligible?</summary><p>No. The assistant can help interpret available documents, but it does not make an official eligibility decision. Confirm current requirements with the scheme authority.</p></details>
        <details><summary>Which languages can I choose?</summary><p>The chat offers English, Hindi, Urdu, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Hinglish, Roman Hindi, and Roman Urdu responses. Detection is heuristic and answer quality has not been fully evaluated in these languages. Voice availability depends on your browser and installed voices.</p></details>
      </section>
      <footer className="public-footer"><Link className="public-brand" to="/"><span className="brand-mark"><ShieldCheck size={18} /></span>Yojana Sahayak</Link><span>Independent information assistant. Not an official government portal.</span><nav><Link to="/about">About</Link><Link to="/documents">Document library</Link><Link to="/login">Sign in</Link></nav></footer>
    </main>
  );
}
