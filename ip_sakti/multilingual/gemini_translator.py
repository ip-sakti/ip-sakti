"""
ip_sakti.multilingual.gemini_translator — Remote Gemini-based translation service.

Reuses the existing Google Gemini API integration (GEMINI_API_KEY) to provide
lightweight, high-quality, production-safe translation for Telugu (te) and
Kannada (kn) text queries and answers without importing any local ML dependencies.

Approved per AGENTS.md §5 and architecture rules.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Sequence

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

from ip_sakti.multilingual.exceptions import TranslationError
from ip_sakti.utils.config import get_settings

logger = logging.getLogger(__name__)

# Pattern to protect/restore citation markers such as [SOURCE_1]
_CITATION_PATTERN = re.compile(r"\[SOURCE_\d+\]")

# Candidate models for translation (in order of priority)
_DEFAULT_MODELS: list[str] = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]

_LANG_INFO: dict[str, dict[str, str]] = {
    "te": {
        "name": "Telugu",
        "native": "తెలుగు",
        "script": "Telugu script (తెలుగు లిపి)",
    },
    "kn": {
        "name": "Kannada",
        "native": "ಕನ್ನಡ",
        "script": "Kannada script (ಕನ್ನಡ ಲಿಪಿ)",
    },
    "en": {
        "name": "English",
        "native": "English",
        "script": "Latin script",
    },
    "hi": {
        "name": "Hindi",
        "native": "हिन्दी",
        "script": "Devanagari script",
    },
}

# Controlled localized fallback error messages if all remote APIs fail
_CONTROLLED_FAILURES: dict[str, str] = {
    "te": "క్షమించండి, అనువాద సేవ ప్రస్తుతం అందుబాటులో లేదు. దయచేసి కాసేపటి తర్వాత మళ్లీ ప్రయత్నించండి.",
    "kn": "ಕ್ಷಮಿಸಿ, ಅನುವಾದ ಸೇವೆ ಪ್ರಸ್ತುತ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
}


class GeminiTranslator:
    """
    Lightweight Gemini-backed translation adapter.
    """

    def __init__(self, api_key: str | None = None) -> None:
        cfg = get_settings()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        configured_model = os.getenv("GEMINI_TRANSLATION_MODEL")
        if not configured_model:
            cfg_model = cfg.get("models", {}).get("llm_model")
            if cfg_model and not any(x in cfg_model.lower() for x in ["tts", "audio", "image"]):
                configured_model = cfg_model
        
        self.models_to_try: list[str] = []
        if configured_model and not any(x in configured_model.lower() for x in ["tts", "audio", "image"]):
            if configured_model not in self.models_to_try:
                self.models_to_try.append(configured_model)
        for m in _DEFAULT_MODELS:
            if m not in self.models_to_try:
                self.models_to_try.append(m)

        self._configured = False
        if self.api_key and _GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self._configured = True
            except Exception as exc:
                logger.warning(f"Failed to configure GeminiTranslator with google.generativeai: {exc}")

    def is_available(self) -> bool:
        """Check if Gemini translator is configured."""
        return bool(self._configured and _GENAI_AVAILABLE)

    def _call_gemini_with_fallback(self, prompt: str, system_instruction: str = "") -> str:
        """Execute a prompt with model fallbacks."""
        if not self.is_available():
            raise TranslationError("Gemini API is not configured or unavailable.")

        last_error = None
        for model_name in self.models_to_try:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction or None,
                )
                generation_config = genai.types.GenerationConfig(
                    max_output_tokens=3072,
                    temperature=0.0,
                )
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"Gemini translation failed on model {model_name}: {exc}. Trying next candidate..."
                )
                continue

        raise TranslationError(f"All Gemini translation models failed. Last error: {last_error}")

    def translate_query_to_english(self, text: str, source_lang: str) -> str:
        """
        Translate a non-English user query (Telugu or Kannada) into English for RAG retrieval.
        """
        src = source_lang.lower().strip()
        if src == "en" or not text.strip():
            return text

        info = _LANG_INFO.get(src, {"name": src.upper(), "script": f"{src} script", "native": src})
        lang_name = info["name"]
        system_instruction = (
            "You are an expert multilingual legal and regulatory translator specializing in Indian "
            "traditional medicine (AYUSH, Ayurveda, Siddha, Unani), patent law, and intellectual property. "
            "Translate the user query into a precise, natural English search query. "
            "Preserve specialized terminology (e.g., Ayurvedic formulations, ASU, Form 24D, Rule 158-B, "
            "patents, TKDL, biological resources, ABS, Schedule T, GMP). "
            "Output ONLY the English translation without any surrounding quotation marks, markdown formatting, or preamble."
        )

        user_prompt = f"Translate the following {lang_name} query into English:\n{text.strip()}"
        translated = self._call_gemini_with_fallback(user_prompt, system_instruction)
        
        # Clean potential quotes
        cleaned = re.sub(r'^["\']|["\']$', '', translated).strip()
        return cleaned or text

    def translate_answer(self, text: str, target_lang: str) -> str:
        """
        Translate an English response into the target language (Telugu or Kannada).
        Preserves citation tags ([SOURCE_1], [SOURCE_2]), statutory references, and URLs.
        """
        tgt = target_lang.lower().strip()
        if tgt == "en" or not text.strip():
            return text

        info = _LANG_INFO.get(tgt, {"name": tgt.upper(), "script": f"{tgt} script", "native": tgt})
        lang_name = info["name"]
        lang_script = info["script"]

        system_instruction = (
            f"You are a professional legal, regulatory, and scientific translator for {lang_name} ({info['native']}). "
            f"Translate the provided English research synthesis into clear, formal, and authoritative {lang_name}.\n\n"
            f"CRITICAL SCRIPT REQUIREMENT:\n"
            f"- You MUST write the translation exclusively in the {lang_script}. "
            f"- Do NOT use Tamil, Malayalam, Hindi, or any other Indic script.\n\n"
            "STRICT QUALITY & PRESERVATION RULES:\n"
            "1. CITATIONS: You MUST preserve citation markers such as [SOURCE_1], [SOURCE_2], [SOURCE_15] exactly as-is. "
            "NEVER translate, modify, or remove citation brackets or numbers.\n"
            "2. URLS: Never translate URLs or web links (e.g. https://ayush.gov.in). Leave them untouched.\n"
            "3. STATUTORY & TECHNICAL CODES: Keep statutory references, form designations, and standard legal codes intact "
            "(e.g., Form 24D, Form 25D, Rule 158-B, Section 3(p), Section 3(e), Schedule T, GMP, AYUSH, ASU, TKDL).\n"
            "4. FORMATTING: Preserve all markdown structures, section headers (###), bullet points, and numbered lists.\n"
            "5. NO PREAMBLE: Return ONLY the translated text in {lang_name}. Do NOT add conversational pleasantries or commentary."
        )

        user_prompt = f"Translate the following text into {lang_name} ({lang_script}):\n\n{text}"
        
        try:
            translated = self._call_gemini_with_fallback(user_prompt, system_instruction)
            if not translated:
                raise TranslationError("Gemini returned empty translation response.")
            return translated
        except Exception as exc:
            logger.error(f"Failed to translate answer to {target_lang} via Gemini: {exc}")
            # If target language is Telugu or Kannada, provide a controlled same-language message
            # rather than silently reverting to English.
            if tgt in _CONTROLLED_FAILURES:
                logger.warning(f"Returning controlled same-language error message for {tgt}")
                return _CONTROLLED_FAILURES[tgt]
            raise
