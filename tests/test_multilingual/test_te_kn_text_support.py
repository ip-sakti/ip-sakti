"""
tests/test_multilingual/test_te_kn_text_support.py — Verification of Telugu and Kannada text support.
"""

from __future__ import annotations

import pytest

from ip_sakti.models.query import QueryRequest
from ip_sakti.multilingual.gemini_translator import GeminiTranslator
from ip_sakti.multilingual.service import MultilingualService
from ip_sakti.multilingual.translator import QueryTranslator


class TestTeluguKannadaTranslation:
    def test_gemini_translator_initializes(self) -> None:
        gt = GeminiTranslator()
        assert gt is not None

    def test_query_translator_has_gemini(self) -> None:
        qt = QueryTranslator()
        assert hasattr(qt, "_gemini_translator")
        assert qt._gemini_translator is not None

    def test_service_prioritizes_explicit_telugu_language(self) -> None:
        service = MultilingualService()
        req = QueryRequest(
            raw_query="ఆయుర్వేద ఔషధ తయారీకి లైసెన్సింగ్ అవసరాలు ఏమిటి?",
            user_language="te",
        )
        ctx = service.process(req)
        assert ctx.effective_language == "te"
        assert ctx.detection.language == "te"
        assert ctx.detection.confidence == 1.0

    def test_service_prioritizes_explicit_kannada_language(self) -> None:
        service = MultilingualService()
        req = QueryRequest(
            raw_query="ಆಯುರ್ವೇದ ಔಷಧ ತಯಾರಿಕೆಗೆ ಪರವಾನಗಿ ಅಗತ್ಯತೆಗಳು ಯಾವುವು?",
            user_language="kn",
        )
        ctx = service.process(req)
        assert ctx.effective_language == "kn"
        assert ctx.detection.language == "kn"
        assert ctx.detection.confidence == 1.0

    def test_service_prioritizes_explicit_english_language(self) -> None:
        service = MultilingualService()
        req = QueryRequest(
            raw_query="What are the licensing requirements?",
            user_language="en",
        )
        ctx = service.process(req)
        assert ctx.effective_language == "en"
        assert ctx.detection.language == "en"
        assert ctx.detection.confidence == 1.0
