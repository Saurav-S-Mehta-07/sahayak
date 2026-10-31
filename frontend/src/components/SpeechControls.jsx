import { useEffect, useMemo, useState } from "react";
import { Pause, Play, Square } from "lucide-react";

const LANGUAGE_LOCALES = {
  en: "en",
  hi: "hi",
  ur: "ur",
  bn: "bn",
  ta: "ta",
  te: "te",
  mr: "mr",
  gu: "gu",
  kn: "kn",
  ml: "ml",
  pa: "pa",
  hinglish: "hi",
  roman_hindi: "hi",
  roman_urdu: "ur",
};

function speechText(markdown) {
  return markdown
    .replace(/【\d+(?:†[^】]*)?】|\[\d+\]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[`*_>#]/g, "")
    .trim();
}

export default function SpeechControls({ text, language = "en" }) {
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState("");
  const [status, setStatus] = useState("");
  const [playing, setPlaying] = useState(false);
  const [paused, setPaused] = useState(false);
  const locale = LANGUAGE_LOCALES[language] || "en";
  const availableVoices = useMemo(
    () => voices.filter((voice) => voice.lang.toLowerCase().startsWith(locale)),
    [locale, voices],
  );
  const selectedVoice = availableVoices.find((voice) => voice.name === voiceName)
    || availableVoices[0];

  useEffect(() => {
    if (!("speechSynthesis" in window)) {
      setStatus("Text-to-speech is not available in this browser; the written answer remains available.");
      return undefined;
    }
    const updateVoices = () => setVoices(window.speechSynthesis.getVoices());
    updateVoices();
    window.speechSynthesis.addEventListener?.("voiceschanged", updateVoices);
    return () => {
      window.speechSynthesis.removeEventListener?.("voiceschanged", updateVoices);
      window.speechSynthesis.cancel();
    };
  }, []);

  function play() {
    if (!("speechSynthesis" in window)) {
      setStatus("Text-to-speech is not available in this browser; the written answer remains available.");
      return;
    }
    if (!selectedVoice) {
      setStatus(`No installed browser voice was found for ${language}. The written answer is still available.`);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(speechText(text));
    utterance.lang = selectedVoice.lang;
    utterance.voice = selectedVoice;
    utterance.onstart = () => {
      setPlaying(true);
      setPaused(false);
      setStatus("");
    };
    utterance.onend = () => {
      setPlaying(false);
      setPaused(false);
    };
    utterance.onerror = (event) => {
      setPlaying(false);
      setPaused(false);
      if (event.error !== "canceled" && event.error !== "interrupted") {
        setStatus("The browser could not play this answer. The written answer remains available.");
      }
    };
    window.speechSynthesis.speak(utterance);
  }

  function pauseOrResume() {
    if (paused) {
      window.speechSynthesis.resume();
      setPaused(false);
    } else {
      window.speechSynthesis.pause();
      setPaused(true);
    }
  }

  function stop() {
    window.speechSynthesis?.cancel();
    setPlaying(false);
    setPaused(false);
  }

  return (
    <div className="speech-playback">
      <button type="button" onClick={play} aria-label="Play answer aloud" title="Play answer aloud">
        <Play size={14} /> Read aloud
      </button>
      {playing && (
        <>
          <button type="button" onClick={pauseOrResume} aria-label={paused ? "Resume speech" : "Pause speech"} title={paused ? "Resume" : "Pause"}>
            {paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          <button type="button" onClick={stop} aria-label="Stop speech" title="Stop">
            <Square size={13} />
          </button>
        </>
      )}
      {availableVoices.length > 1 && (
        <label>
          <span className="sr-only">Select speech voice</span>
          <select value={selectedVoice?.name || ""} onChange={(event) => setVoiceName(event.target.value)}>
            {availableVoices.map((voice) => (
              <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                {voice.name} ({voice.lang})
              </option>
            ))}
          </select>
        </label>
      )}
      {status && <span className="speech-status-inline" role="status">{status}</span>}
    </div>
  );
}
