import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Check,
  Copy,
  FileText,
  MessageCircle,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { motion } from "framer-motion";
import SourceCard from "./SourceCard.jsx";
import SpeechControls from "./SpeechControls.jsx";
import { getDisplayLocale } from "../utils/language.js";

function timestamp(value, language) {
  const locale = getDisplayLocale(language);
  return new Intl.DateTimeFormat(locale, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function linkCitations(markdown, idPrefix) {
  return markdown.replace(/【(\d+)(?:†[^】]*)?】|\[(\d+)\]/g, (match, a, b) => {
    const number = a || b;
    return `[${number}](#source-${idPrefix}-${number})`;
  });
}

export default function ChatMessage({
  message,
  onRetry,
  onSourceOpen,
  onRegenerate,
  isLastAssistant,
}) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const isAssistant = message.role === "assistant";
  const content = useMemo(
    () => (isAssistant ? linkCitations(message.content, message.id) : message.content),
    [isAssistant, message.content, message.id],
  );

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <motion.article
      className={`message-row ${isAssistant ? "message-assistant" : "message-user"}`}
      initial={{ opacity: 0, y: 9 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24 }}
    >
      {isAssistant && <div className="assistant-avatar" aria-label="Yojana Sahayak"><MessageCircle size={16} /></div>}
      <div className="message-body">
        <div className="message-meta">
          <strong>{isAssistant ? "Yojana Sahayak" : "You"}</strong>
          <time dateTime={message.createdAt}>{timestamp(message.createdAt, message.language)}</time>
        </div>
        <div className={`message-bubble ${isAssistant ? "assistant-bubble" : "user-bubble"}`}>
          {isAssistant ? (
            <div className="markdown-answer" lang={getDisplayLocale(message.language)} dir={message.direction || "auto"}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a({ href = "", children, ...props }) {
                    if (href.startsWith("#source-")) {
                      return (
                        <a
                          href={href}
                          onClick={(event) => {
                            event.preventDefault();
                            document.getElementById(href.slice(1))?.scrollIntoView({
                              behavior: "smooth",
                              block: "center",
                            });
                          }}
                        >
                          {children}
                        </a>
                      );
                    }
                    return <a href={href} target="_blank" rel="noreferrer" {...props}>{children}</a>;
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          ) : <p>{message.content}</p>}
          {message.failed && (
            <div className="message-failed">
              <span>Your question wasn’t sent.</span>
              <button onClick={() => onRetry(message)}>Try again</button>
            </div>
          )}
          {isAssistant && (
            <div className="message-actions">
              <SpeechControls text={message.content} language={message.language} />
              <button onClick={copyAnswer} aria-label="Copy answer" title="Copy answer">{copied ? <Check size={14} /> : <Copy size={14} />}</button>
              {isLastAssistant && (
                <button onClick={onRegenerate} aria-label="Regenerate answer" title="Regenerate answer"><RotateCcw size={14} /></button>
              )}
              <span className="action-spacer" />
              <button className={feedback === "up" ? "feedback-active" : ""} onClick={() => setFeedback(feedback === "up" ? null : "up")} aria-label="Helpful answer" title="Helpful"><ThumbsUp size={14} /></button>
              <button className={feedback === "down" ? "feedback-active" : ""} onClick={() => setFeedback(feedback === "down" ? null : "down")} aria-label="Not helpful" title="Not helpful"><ThumbsDown size={14} /></button>
            </div>
          )}
        </div>
        {isAssistant && (
          <section className="sources-section" aria-label="Retrieved document evidence">
            <div className="sources-heading">
              <FileText size={14} /><span>Retrieved document evidence</span>
              <span className="sources-count">{message.sources?.length ?? 0}</span>
            </div>
            {!message.sources?.length ? (
              <p className="no-sources">No supporting source documents were returned. This answer should not be treated as document-verified scheme guidance.</p>
            ) : (
              <div className="sources-list">
                {message.sources.map((source, index) => (
                  <SourceCard
                    key={`${source.source || source.filename}-${source.page}-${index}`}
                    source={source}
                    index={index}
                    idPrefix={message.id}
                    displayLocale={getDisplayLocale(message.language)}
                    onOpen={onSourceOpen}
                  />
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </motion.article>
  );
}
