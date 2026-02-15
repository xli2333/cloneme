from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.config import settings
from app.services.evolution import EvolutionService
from app.services.generation import GenerationService
from app.services.persona import normalize_persona_payload, persona_brief


class PersonaMemoryFlowTests(unittest.TestCase):
    def test_normalize_legacy_payload(self) -> None:
        legacy = {
            "identity": {"name": "Doppelganger"},
            "relationship": {"strict_nickname": "宝贝"},
            "speech_traits": {"top_phrases": ["我在"]},
        }
        norm = normalize_persona_payload(legacy)
        self.assertIn("core_persona", norm)
        self.assertIn("adaptive_persona", norm)
        self.assertEqual(norm["core_persona"]["relationship"]["strict_nickname"], "宝贝")

    def test_persona_brief_phrase_limit(self) -> None:
        raw = {
            "core_persona": {"relationship": {"strict_nickname": "宝贝"}},
            "adaptive_persona": {"speech_traits": {"top_phrases": [f"p{i}" for i in range(30)]}},
        }
        brief = persona_brief(raw, phrase_limit=10)
        self.assertEqual(len(brief["speech_traits"]["top_phrases"]), 10)

    def test_generation_persona_cache(self) -> None:
        svc = GenerationService()
        style_row = {"payload": {"avg_len": 8}}
        pref_row = {"payload": {"weights": {"semantic": 0.45}}}
        persona_row = {"payload": {"core_persona": {}, "adaptive_persona": {}}, "version": 1}
        old_ttl = settings.persona_cache_ttl_sec
        settings.persona_cache_ttl_sec = 600
        try:
            with (
                patch("app.services.generation.db.get_profile", side_effect=[style_row, pref_row, style_row, pref_row, style_row, pref_row]),
                patch("app.services.generation.db.get_persona_profile", side_effect=[persona_row, persona_row]) as mock_persona,
                patch("app.services.generation.time.monotonic", side_effect=[0.0, 1.0, 700.0]),
            ):
                svc._load_profiles()
                svc._load_profiles()
                svc._load_profiles()
            self.assertEqual(mock_persona.call_count, 2)
        finally:
            settings.persona_cache_ttl_sec = old_ttl

    def test_evolution_candidate_promote_gate(self) -> None:
        svc = EvolutionService()
        old_min_samples = settings.persona_candidate_min_samples
        old_min_freq = settings.persona_candidate_min_phrase_freq
        old_limit = settings.persona_adaptive_top_phrases_limit
        settings.persona_candidate_min_samples = 5
        settings.persona_candidate_min_phrase_freq = 2
        settings.persona_adaptive_top_phrases_limit = 20
        persona_row_v1 = {
            "version": 1,
            "payload": {
                "core_persona": {"relationship": {"forbidden_nicknames": ["老婆"]}},
                "adaptive_persona": {"speech_traits": {"top_phrases": ["我在"]}},
            },
        }
        persona_row_v2 = {
            "version": 2,
            "payload": {
                "core_persona": {"relationship": {"forbidden_nicknames": ["老婆"]}},
                "adaptive_persona": {"speech_traits": {"top_phrases": ["我在", "先接住你"]}},
            },
        }
        try:
            with (
                patch("app.services.evolution.db.get_persona_profile", side_effect=[persona_row_v1, persona_row_v2]) as mock_get_persona,
                patch("app.services.evolution.db.get_profile", return_value={"payload": {"sample_count": 4, "phrase_scores": {"先接住你": 1}}}),
                patch("app.services.evolution.db.upsert_profile") as mock_upsert_profile,
                patch("app.services.evolution.db.upsert_persona_profile") as mock_upsert_persona,
            ):
                version = svc._update_persona_from_samples(["先接住你", "先接住你"])
            self.assertEqual(version, 2)
            self.assertTrue(mock_upsert_persona.called)
            self.assertGreaterEqual(mock_upsert_profile.call_count, 2)
            self.assertEqual(mock_get_persona.call_count, 2)
        finally:
            settings.persona_candidate_min_samples = old_min_samples
            settings.persona_candidate_min_phrase_freq = old_min_freq
            settings.persona_adaptive_top_phrases_limit = old_limit


if __name__ == "__main__":
    unittest.main()
