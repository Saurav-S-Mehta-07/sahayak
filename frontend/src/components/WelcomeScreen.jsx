import { ArrowUpRight, FileSearch, Landmark, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";

const suggestedQuestions = [
  "What government schemes are available in these documents?",
  "What are the eligibility requirements?",
  "Which documents are required to apply?",
  "How can I apply for a particular scheme?",
];

export default function WelcomeScreen({ onAsk }) {
  return (
    <div className="welcome-wrap">
      <motion.div
        className="welcome-content"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.38 }}
      >
        <div className="welcome-illustration" aria-hidden="true">
          <div className="illustration-orbit orbit-one" />
          <div className="illustration-orbit orbit-two" />
          <div className="illustration-center"><Landmark size={35} strokeWidth={1.35} /></div>
          <div className="illustration-chip chip-file"><FileSearch size={16} /></div>
          <div className="illustration-chip chip-check"><ShieldCheck size={16} /></div>
          <span className="illustration-spark spark-one" />
          <span className="illustration-spark spark-two" />
        </div>
        <span className="eyebrow"><span className="eyebrow-dot" /> DOCUMENT-GROUNDED ASSISTANCE</span>
        <h1>Your guide to<br /><span>government schemes.</span></h1>
        <p className="welcome-copy">
          Ask about eligibility, benefits, required documents, and application
          procedures. Get clear answers grounded in the documents available to
          this assistant.
        </p>
        <div className="suggestion-grid">
          {suggestedQuestions.map((question, index) => (
            <motion.button
              key={question}
              className="suggestion-card"
              onClick={() => onAsk(question)}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.985 }}
              transition={{ duration: 0.16 }}
            >
              <span className="suggestion-index">0{index + 1}</span>
              <span>{question}</span>
              <ArrowUpRight size={16} className="suggestion-arrow" />
            </motion.button>
          ))}
        </div>
        <div className="trust-note">
          <ShieldCheck size={15} />
          <span>Answers use retrieved scheme documents with source references.</span>
        </div>
      </motion.div>
    </div>
  );
}
