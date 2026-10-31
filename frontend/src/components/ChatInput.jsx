import { useEffect, useRef, useState } from "react";
import { ArrowUp, Mic, MicOff, X } from "lucide-react";

const MAX_LENGTH = 1500;
const SPEECH_LOCALES = {
  auto: "en-IN",
  en: "en-IN",
  hi: "hi-IN",
  ur: "ur-PK",
  bn: "bn-IN",
  ta: "ta-IN",
  te: "te-IN",
  mr: "mr-IN",
  gu: "gu-IN",
  kn: "kn-IN",
  ml: "ml-IN",
  pa: "pa-IN",
  hinglish: "hi-IN",
  roman_hindi: "hi-IN",
  roman_urdu: "ur-PK",
};

export default function ChatInput({ onSubmit, disabled, language }) {
  const [value, setValue] = useState("");
  const [recording, setRecording] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);
  const startingTextRef = useRef("");
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => () => recognitionRef.current?.abort(), []);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [value]);

  function submit(event) {
    event?.preventDefault();
    const query = value.trim();
    if (!query || disabled) return;
    onSubmit(query);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function toggleRecording() {
    if (recording) {
      recognitionRef.current?.stop();
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setSpeechError("Speech recognition is not available in this browser. You can still type your question.");
      return;
    }
    setSpeechError("");
    try {
      const recognition = new Recognition();
      recognition.lang = SPEECH_LOCALES[language] || "en-IN";
      recognition.continuous = false;
      recognition.interimResults = true;
      startingTextRef.current = valueRef.current
        ? `${valueRef.current.trim()} `
        : "";
      recognition.onstart = () => setRecording(true);
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((result) => result[0]?.transcript || "")
          .join("");
        setValue(`${startingTextRef.current}${transcript}`.slice(0, MAX_LENGTH));
        setSpeechError("");
      };
      recognition.onerror = (event) => {
        setRecording(false);
        const messages = {
          "not-allowed": "Microphone permission was denied. Allow microphone access in browser settings or type your question.",
          "service-not-allowed": "The browser speech service is unavailable. You can type your question instead.",
          "no-speech": "No speech was detected. Try again or type your question.",
          "language-not-supported": "This browser does not support speech recognition for the selected language. You can type your question.",
        };
        setSpeechError(messages[event.error] || "Speech recognition stopped unexpectedly. Please try again or type your question.");
      };
      recognition.onend = () => setRecording(false);
      recognitionRef.current = recognition;
      recognition.start();
    } catch {
      setRecording(false);
      setSpeechError("Could not start microphone recognition. Check microphone permission and try again.");
    }
  }

  return (
    <div className="composer-wrap">
      {speechError && <p className="speech-status" role="status">{speechError}</p>}
      {recording && <p className="speech-status speech-recording" role="status">Listening in {SPEECH_LOCALES[language] || "English"}… Speak now; the transcript is editable.</p>}
      <form className="composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">Ask anything about government schemes</label>
        <textarea
          ref={textareaRef}
          id="chat-input"
          value={value}
          onChange={(event) => setValue(event.target.value.slice(0, MAX_LENGTH))}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="Ask anything about government schemes..."
          dir={language === "ur" ? "rtl" : "auto"}
          rows={1}
          maxLength={MAX_LENGTH}
          disabled={disabled}
          aria-describedby="composer-hint"
        />
        <div className="composer-controls">
          <span className="composer-hint" id="composer-hint">
            {value.length > 1000 ? `${value.length}/${MAX_LENGTH}` : "Shift + Enter for a new line"}
          </span>
          {value.length > 0 && (
            <button type="button" className="composer-clear" onClick={() => setValue("")} aria-label="Clear message" disabled={disabled}>
              <X size={15} />
            </button>
          )}
          <button
            type="button"
            className={`speech-button ${recording ? "speech-button-active" : ""}`}
            onClick={toggleRecording}
            disabled={disabled}
            aria-label={recording ? "Stop speech recognition" : "Start speech recognition"}
            title={recording ? "Stop recording" : "Dictate a question"}
          >
            {recording ? <MicOff size={16} /> : <Mic size={16} />}
          </button>
          <button type="submit" className="send-button" aria-label="Send message" disabled={disabled || !value.trim()}>
            {disabled ? <span className="button-spinner" /> : <ArrowUp size={18} />}
          </button>
        </div>
      </form>
      <p className="disclaimer">
        Document-based information only. Browser speech recognition availability and accuracy vary by language and browser. Verify eligibility and application details with the official authority.
      </p>
    </div>
  );
}
