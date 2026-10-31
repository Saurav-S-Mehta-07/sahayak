import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertCircle, Trash2, X } from "lucide-react";
import ChatInput from "../components/ChatInput.jsx";
import ChatMessage from "../components/ChatMessage.jsx";
import TypingIndicator from "../components/TypingIndicator.jsx";
import WelcomeScreen from "../components/WelcomeScreen.jsx";
import { useChat } from "../context/ChatContext.jsx";
import { getDisplayLocale } from "../utils/language.js";

export default function ChatPage() {
  const { activeChat, pending, historyError, submit, retryMessage, regenerate, clearChat, language } = useChat();
  const location = useLocation();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [selectedSource, setSelectedSource] = useState(null);
  const scrollRef = useRef(null);
  const sourceDialogRef = useRef(null);
  const prefillConsumed = useRef(false);
  const messages = activeChat?.messages ?? [];

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length, pending]);

  useEffect(() => {
    const prompt = location.state?.prefill;
    if (!prompt || prefillConsumed.current) return;
    prefillConsumed.current = true;
    navigate("/chat", { replace: true, state: null });
    void ask(prompt);
  }, [location.state, navigate]);

  useEffect(() => {
    if (!selectedSource) return undefined;
    const previousFocus = document.activeElement;
    sourceDialogRef.current?.focus();
    const handleDialogKeys = (event) => {
      if (event.key === "Escape") {
        setSelectedSource(null);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = sourceDialogRef.current?.querySelectorAll(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleDialogKeys);
    return () => {
      window.removeEventListener("keydown", handleDialogKeys);
      previousFocus?.focus?.();
    };
  }, [selectedSource]);

  async function ask(query) {
    setError("");
    const result = await submit(query);
    if (result && !result.ok) setError(result.error);
  }

  async function retry(message) {
    setError("");
    const result = await retryMessage(message);
    if (result && !result.ok) setError(result.error);
  }

  async function regenerateAnswer() {
    setError("");
    const result = await regenerate();
    if (result && !result.ok) setError(result.error);
  }

  async function clearConversation() {
    if (!activeChat || !messages.length) return;
    if (!window.confirm("Clear all messages in this conversation? This cannot be undone.")) return;
    setError("");
    const result = await clearChat(activeChat.id);
    if (!result.ok) setError(result.error);
  }

  return (
    <div className="chat-page">
      {messages.length > 0 && (
        <div className="chat-toolbar">
          <span>{activeChat?.title}</span>
          <button type="button" className="chat-clear-button" onClick={clearConversation} disabled={pending}>
            <Trash2 size={14} /> Clear chat
          </button>
        </div>
      )}
      <div className={`chat-scroll ${messages.length ? "chat-scroll-filled" : ""}`} ref={scrollRef}>
        {messages.length === 0 ? (
          <WelcomeScreen onAsk={ask} />
        ) : (
          <div className="message-feed" role="log" aria-live="polite" aria-relevant="additions text" aria-label="Conversation messages">
            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                onRetry={retry}
                onSourceOpen={(source) => setSelectedSource({
                  ...source,
                  displayLocale: getDisplayLocale(message.language),
                })}
                onRegenerate={regenerateAnswer}
                isLastAssistant={
                  message.role === "assistant" &&
                  !messages.slice(index + 1).some((item) => item.role === "assistant")
                }
              />
            ))}
            {pending && <TypingIndicator />}
          </div>
        )}
      </div>

      {error && (
        <div className="error-banner" role="alert">
          <AlertCircle size={16} /><span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button>
        </div>
      )}
      {!error && historyError && (
        <div className="error-banner" role="alert">
          <AlertCircle size={16} /><span>{historyError}</span>
        </div>
      )}
      <ChatInput onSubmit={ask} disabled={pending} language={language} />

      {selectedSource && (
        <div className="source-modal-scrim" role="presentation" onClick={() => setSelectedSource(null)}>
          <section
            className="source-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-modal-title"
            tabIndex={-1}
            ref={sourceDialogRef}
            onClick={(event) => event.stopPropagation()}
          >
            <button className="icon-button source-modal-close" onClick={() => setSelectedSource(null)} aria-label="Close source details">
              <X size={18} />
            </button>
            <span className="eyebrow">RETRIEVED DOCUMENT PASSAGE</span>
            <h2 id="source-modal-title">{selectedSource.filename || "Source document"}</h2>
            {selectedSource.scheme_name && <p className="source-detail-page">{selectedSource.scheme_name}</p>}
            {selectedSource.page !== null && selectedSource.page !== undefined && (
              <p className="source-detail-page">Page {new Intl.NumberFormat(
                selectedSource.displayLocale,
                { useGrouping: false },
              ).format(Number(selectedSource.page) + 1)}</p>
            )}
            <blockquote>{selectedSource.content || "No passage was returned for this source."}</blockquote>
            {selectedSource.source_url ? (
              <a className="source-detail-link" href={selectedSource.source_url} target="_blank" rel="noreferrer">
                Open official document source
              </a>
            ) : (
              <p className="source-detail-note">This passage was returned by the document retrieval system. No official source URL is available for this indexed document.</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
