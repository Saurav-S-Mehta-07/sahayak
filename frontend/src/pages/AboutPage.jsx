import { FileSearch, Languages, ShieldCheck } from "lucide-react";

const principles = [
  {
    icon: FileSearch,
    title: "Grounded in documents",
    text: "Answers and source passages come from the documents indexed by the connected RAG backend. The document explorer reflects its current metadata.",
  },
  {
    icon: ShieldCheck,
    title: "Verify important details",
    text: "This assistant is an informational tool, not a government authority. Confirm eligibility, deadlines, and application steps with the responsible official department.",
  },
  {
    icon: Languages,
    title: "Language support",
    text: "You can enter questions in English, Hindi, or Hinglish. The current backend does not expose a separate response-language control, so the interface preference does not translate answers.",
  },
];

export default function AboutPage() {
  return (
    <section className="documents-page about-page">
      <div className="documents-heading">
        <div>
          <span className="eyebrow"><span className="eyebrow-dot" /> YOJANA SAHAYAK</span>
          <h1>Government schemes.<br />Clear answers. Trusted sources.</h1>
          <p>A document-grounded assistant for exploring scheme information.</p>
        </div>
      </div>
      <div className="principle-grid">
        {principles.map(({ icon: Icon, title, text }) => (
          <article className="principle-card" key={title}>
            <span className="principle-icon"><Icon size={18} /></span>
            <h2>{title}</h2>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <p className="about-footnote">
        Yojana Sahayak is not an official government website and does not submit
        applications or determine eligibility.
      </p>
    </section>
  );
}
