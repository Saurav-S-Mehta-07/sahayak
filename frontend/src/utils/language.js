const DISPLAY_LOCALES = {
  en: "en-IN",
  hi: "hi-IN",
  ur: "ur-PK",
  bn: "bn-BD",
  ta: "ta-IN",
  te: "te-IN",
  mr: "mr-IN",
  gu: "gu-IN",
  kn: "kn-IN",
  ml: "ml-IN",
  pa: "pa-IN",
  hinglish: "hi-IN",
  roman_hindi: "hi-Latn-IN",
  roman_urdu: "ur-Latn-PK",
};

export function getDisplayLocale(language) {
  return DISPLAY_LOCALES[language];
}
