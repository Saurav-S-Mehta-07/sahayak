import { motion } from "framer-motion";

export default function TypingIndicator() {
  return (
    <div className="typing-row" role="status" aria-label="Yojana Sahayak is preparing an answer">
      <div className="assistant-avatar"><span className="typing-logo">YS</span></div>
      <div className="typing-card">
        <span>Searching scheme documents</span>
        <span className="typing-dots">
          {[0, 1, 2].map((dot) => (
            <motion.i
              key={dot}
              animate={{ opacity: [0.35, 1, 0.35], y: [0, -2, 0] }}
              transition={{ duration: 0.9, repeat: Infinity, delay: dot * 0.16 }}
            />
          ))}
        </span>
      </div>
    </div>
  );
}
