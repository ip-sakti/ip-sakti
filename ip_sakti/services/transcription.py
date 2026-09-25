"""
Voice Input / Speech-to-Text Service for IP-SAKTI Sahayak

Supports English-only Speech-to-Text (STT):
- English ('en') -> Pretrained Whisper 'base' model (lazy-loaded)
- All non-English requests -> Rejected without model loading

Includes 16 kHz mono WAV audio normalization and lazy model caching.
"""

import os
import sys
import shutil
import tempfile
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

# Ensure HF_HOME points to a valid local directory
try:
    hf_cache = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    os.makedirs(hf_cache, exist_ok=True)
    os.environ["HF_HOME"] = hf_cache
    os.environ["TRANSFORMERS_CACHE"] = hf_cache
except Exception as hf_err:
    logger.warning(f"Could not set HF_HOME cache dir: {hf_err}")

# Ensure ffmpeg binary from imageio-ffmpeg is copied as ffmpeg.exe and added to PATH
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(target_ffmpeg) and os.path.exists(ffmpeg_exe):
        try:
            shutil.copy2(ffmpeg_exe, target_ffmpeg)
            logger.info(f"Copied {ffmpeg_exe} -> {target_ffmpeg}")
        except Exception as copy_err:
            logger.warning(f"Could not copy ffmpeg.exe: {copy_err}")
            
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.path.pathsep + os.environ.get("PATH", "")
        logger.info(f"Added ffmpeg directory to PATH: {ffmpeg_dir}")
except Exception as e:
    logger.warning(f"Could not load imageio-ffmpeg helper: {e}")

_WHISPER_MODEL = None
_QUERY_TRANSLATOR = None

SUPPORTED_VOICE_LANGUAGES = {"en"}

LANG_CODE_MAP = {
    "en": "en", "eng": "en", "english": "en", "en-in": "en", "en-us": "en",
}

COMMON_ENGLISH_KEYWORDS = {
    "what", "how", "which", "why", "where", "is", "are", "can", "to", "for",
    "in", "of", "and", "the", "a", "an", "permission", "permissions", "license",
    "licence", "manufacture", "manufacturing", "make", "selling", "product",
    "medicine", "drug", "ayurvedic", "ayurveda", "formulation", "requirement",
    "requirements", "rule", "rules", "act", "patent", "patents"
}


def get_whisper_model(model_name: str = "base"):
    """
    Lazy-load and return cached singleton instance of Whisper model.
    Default: 'base' for high-accuracy CPU transcription.
    """
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        logger.info(f"Loading Whisper model '{model_name}'...")
        import whisper
        _WHISPER_MODEL = whisper.load_model(model_name)
        logger.info(f"Whisper model '{model_name}' loaded successfully.")
    return _WHISPER_MODEL


def get_query_translator():
    """
    Lazy-load and return cached singleton instance of QueryTranslator.
    """
    global _QUERY_TRANSLATOR
    if _QUERY_TRANSLATOR is None:
        from ip_sakti.multilingual.translator import QueryTranslator
        _QUERY_TRANSLATOR = QueryTranslator()
    return _QUERY_TRANSLATOR


def normalize_audio_to_wav16k(input_path: str) -> str:
    """
    Normalize audio file to mono 16,000 Hz WAV using ffmpeg.
    Returns path to temporary 16kHz mono WAV file.
    """
    wav_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        wav_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
            logger.info(f"Normalized audio to 16kHz WAV: {wav_path} ({os.path.getsize(wav_path)} bytes)")
            return wav_path
        else:
            logger.warning(f"ffmpeg normalization returned non-zero code {res.returncode}. Using input path.")
            return input_path
    except Exception as e:
        logger.warning(f"Audio normalization via ffmpeg failed: {e}. Using input path.")
        return input_path


def is_romanized_gibberish(text: str, source_lang: str) -> bool:
    """
    Detect if text is romanized/transliterated non-English tokens instead of
    true English semantic translation.
    """
    if not text or source_lang == "en":
        return False
        
    text_lower = text.lower()
    
    # Check for known romanized non-English tokens
    romanized_tokens = {"hairovidha", "haushdha", "hayaro", "tanki", "inhon", "madho", "kowali", "banane", "chahiye", "tayaru", "cheyadaniki"}
    words = set(text_lower.split())
    if len(words.intersection(romanized_tokens)) > 0:
        return True

    # If length > 15 chars, genuine English translation should contain common English words/keywords
    if len(text_lower) > 15:
        overlap = words.intersection(COMMON_ENGLISH_KEYWORDS)
        if len(overlap) == 0:
            return True

    return False


def validate_script_consistency(text: str, lang_code: str) -> bool:
    """
    Enforce strict script consistency for the detected language:
    - 'te' (Telugu) MUST contain Telugu script characters (U+0C00–U+0C7F).
    - 'kn' (Kannada) MUST contain Kannada script characters (U+0C80–U+0CFF).
    - 'hi' (Hindi) MUST contain Devanagari script characters (U+0900–U+097F).
    """
    if not text or lang_code == "en":
        return True

    devanagari_count = sum(1 for c in text if '\u0900' <= c <= '\u097f')
    telugu_count = sum(1 for c in text if '\u0c00' <= c <= '\u0c7f')
    kannada_count = sum(1 for c in text if '\u0c80' <= c <= '\u0cff')

    if lang_code == "te" and telugu_count == 0:
        logger.error(f"Script Mismatch / Hallucination: language='te' but zero Telugu characters in '{text}'")
        return False

    if lang_code == "kn" and kannada_count == 0:
        logger.error(f"Script Mismatch / Hallucination: language='kn' but zero Kannada characters in '{text}'")
        return False

    if lang_code == "hi" and devanagari_count == 0:
        logger.error(f"Script Mismatch / Hallucination: language='hi' but zero Devanagari characters in '{text}'")
        return False

    return True


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    content_type: str = None,
    target_lang: str = None
) -> dict:
    """
    Transcribe audio bytes for English voice queries via Whisper Base.
    Rejects non-English requests immediately without model loading.
    
    Args:
        audio_bytes: Raw bytes of recorded audio file.
        filename: Original filename or hint for format extension.
        content_type: MIME type of uploaded audio file.
        target_lang: Authoritative target language code (en).
        
    Returns:
        dict: {
            "transcript": str,
            "language": str,
            "translated_text": str | None,
            "error": str | None
        }
    """
    # ── Authoritative Target Language Check (English Only) ───────────────────
    target_clean = LANG_CODE_MAP.get(target_lang.lower().strip(), target_lang.lower().strip()) if target_lang else "en"
    if target_clean != "en":
        logger.info(f"Non-English voice requested ('{target_lang}'). Rejecting without model loading.")
        return {
            "transcript": "",
            "language": "unsupported",
            "translated_text": None,
            "error": "Voice input is supported in English only."
        }

    if not audio_bytes or len(audio_bytes) < 100:
        return {
            "transcript": "",
            "language": "en",
            "translated_text": None,
            "error": "Audio recording is empty or too short. Please speak again."
        }

    ext = os.path.splitext(filename)[1]
    if not ext or len(ext) > 10:
        ext = ".webm"

    mime = content_type or f"audio/{ext.lstrip('.')}"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    norm_wav_path = None
    t_start = time.time()

    try:
        # ── Audio Normalization (Mono 16 kHz WAV) ─────────────────────────────────
        norm_wav_path = normalize_audio_to_wav16k(tmp_path)

        # ── English STT Execution via Whisper Base ───────────────────────────────
        logger.info("Routing STT to Whisper Base: lang=en")
        model = get_whisper_model("base")
        stt_kwargs = {
            "fp16": False,
            "task": "transcribe",
            "language": "en",
            "temperature": 0.0,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.6,
            "logprob_threshold": -1.0,
            "compression_ratio_threshold": 2.4
        }

        stt_result = model.transcribe(
            norm_wav_path,
            **stt_kwargs
        )
        raw_text = stt_result.get("text", "").strip()

        logger.info(f"STT decoded (Whisper Base, lang=en): '{raw_text}'")

        # Reject empty or no-speech audio
        if not raw_text:
            return {
                "transcript": "",
                "language": "en",
                "translated_text": None,
                "error": "No speech detected in audio. Please try speaking clearly."
            }

        elapsed_time = time.time() - t_start
        print("\n" + "=" * 50, flush=True)
        print("=== VOICE DEBUG ===", flush=True)
        print(f"Selected language: {target_lang or 'en'}", flush=True)
        print("ASR Engine: Whisper Base", flush=True)
        print(f"Audio MIME: {mime}", flush=True)
        print(f"Audio size: {len(audio_bytes)} bytes", flush=True)
        print(f"Inference Time: {elapsed_time:.2f}s", flush=True)
        print(f"TRANSCRIPT:\n{raw_text}", flush=True)
        print("=" * 50 + "\n", flush=True)

        return {
            "transcript": raw_text,
            "language": "en",
            "translated_text": raw_text,
            "error": None
        }

    except Exception as e:
        logger.error(f"Error during audio processing: {e}", exc_info=True)
        return {
            "transcript": "",
            "language": "en",
            "translated_text": None,
            "error": f"Voice processing failed: {str(e)}"
        }
    finally:
        # Immediate cleanup of temporary audio files
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if norm_wav_path and norm_wav_path != tmp_path and os.path.exists(norm_wav_path):
            try:
                os.remove(norm_wav_path)
            except Exception:
                pass
