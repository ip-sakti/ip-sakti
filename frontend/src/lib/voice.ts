/**
 * Web Speech API Text-to-Speech (TTS) Utility for IP-SAKTI Sahayak.
 * Uses native window.speechSynthesis to speak final research answers in English, Hindi, Telugu, or Kannada.
 */

const LANG_CODE_MAP: Record<string, string> = {
  en: 'en-IN',
  'en-in': 'en-IN',
  'en-us': 'en-US',
};

/**
 * Clean text for natural speech synthesis (remove markdown markers, URL icons, citations).
 */
export function cleanTextForTTS(rawText: string): string {
  if (!rawText) return '';
  return rawText
    .replace(/\[\d+\]/g, '') // remove citation brackets [1]
    .replace(/[#*`_~]/g, '') // remove markdown symbols
    .replace(/↗/g, '')
    .replace(/http[s]?:\/\/\S+/g, '') // remove URLs
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Stop any currently active speech synthesis immediately.
 */
export function stopSpeaking(): void {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch (e) {
      console.warn('SpeechSynthesis cancel error:', e);
    }
  }
}

/**
 * Check if browser is currently speaking.
 */
export function isSpeaking(): boolean {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    return window.speechSynthesis.speaking;
  }
  return false;
}

/**
 * Retrieve best available voice for requested BCP-47 language code (en-IN).
 */
export function getVoiceForLanguage(langCode: string): SpeechSynthesisVoice | null {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return null;
  }

  const targetLang = LANG_CODE_MAP[langCode.toLowerCase()] || 'en-IN';
  const voices = window.speechSynthesis.getVoices();

  if (!voices || voices.length === 0) return null;

  // 1. Exact BCP-47 match (e.g. en-IN)
  let best = voices.find(
    (v) => v.lang.toLowerCase().replace('_', '-') === targetLang.toLowerCase()
  );

  // 2. Exact prefix match (e.g. en)
  if (!best) {
    best = voices.find((v) => v.lang.toLowerCase().startsWith('en'));
  }

  return best || voices[0] || null;
}

interface SpeakOptions {
  text: string;
  lang?: string;
  queryText?: string;
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (err: any) => void;
}

/**
 * Speak text aloud using browser Web Speech API (English queries only).
 */
export function speakText({ text, lang = 'en', queryText, onStart, onEnd, onError }: SpeakOptions): void {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    console.warn('SpeechSynthesis API is not supported in this environment.');
    if (onEnd) onEnd();
    return;
  }

  const normLang = (lang || 'en').toLowerCase().split('-')[0];
  const hasNonEnglishScriptInQuery = queryText ? /[\u0900-\u0d7f\u0600-\u06ff]/.test(queryText) : false;

  if (normLang !== 'en' || hasNonEnglishScriptInQuery) {
    // Hard safety guard: Voice output is allowed ONLY for English queries
    stopSpeaking();
    if (onEnd) onEnd();
    return;
  }

  const cleaned = cleanTextForTTS(text);
  if (!cleaned) {
    if (onEnd) onEnd();
    return;
  }

  // 1. Cancel any active speech
  stopSpeaking();

  const bcp47Lang = LANG_CODE_MAP[lang.toLowerCase()] || 'en-IN';
  const utterance = new SpeechSynthesisUtterance(cleaned);
  utterance.lang = bcp47Lang;
  utterance.rate = 0.95; // Slightly natural cadence

  // 2. Assign best matching voice if available
  const matchingVoice = getVoiceForLanguage(lang);
  if (matchingVoice) {
    utterance.voice = matchingVoice;
  }

  utterance.onstart = () => {
    if (onStart) onStart();
  };

  utterance.onend = () => {
    if (onEnd) onEnd();
  };

  utterance.onerror = (evt) => {
    // Ignore interrupted/cancelled speech events
    if (evt.error !== 'interrupted' && evt.error !== 'canceled') {
      console.warn('SpeechSynthesisUtterance error:', evt);
      if (onError) onError(evt);
    }
    if (onEnd) onEnd();
  };

  try {
    // 3. Re-verify English query condition immediately before calling speak
    if (normLang === 'en' && !hasNonEnglishScriptInQuery) {
      window.speechSynthesis.speak(utterance);
    } else {
      stopSpeaking();
      if (onEnd) onEnd();
    }
  } catch (err) {
    console.warn('SpeechSynthesis speak failed:', err);
    if (onEnd) onEnd();
  }
}
