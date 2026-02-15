from __future__ import annotations

import unittest

from app.services.generation import GenerationService


class PersonaGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GenerationService()
        self.persona = {
            "relationship": {
                "strict_nickname": "宝贝",
                "forbidden_nicknames": ["宝宝", "老婆"],
            },
            "speech_traits": {
                "avg_len": 8,
                "top_phrases": ["我在", "先接住你", "慢慢来"],
            },
        }

    def test_forbidden_nickname_should_drop_score(self) -> None:
        safe = ["我在，先接住你这个点。"]
        violated = ["老婆，我马上给你答复。"]
        safe_score = self.service._persona_consistency_score(safe, self.persona)
        violated_score = self.service._persona_consistency_score(violated, self.persona)
        self.assertGreater(safe_score, violated_score)
        self.assertEqual(violated_score, 0.0)

    def test_phrase_alignment_should_help(self) -> None:
        hit = ["我在，先接住你。慢慢来。"]
        miss = ["收到，信息确认完毕。"]
        hit_score = self.service._persona_consistency_score(hit, self.persona)
        miss_score = self.service._persona_consistency_score(miss, self.persona)
        self.assertGreater(hit_score, miss_score)


if __name__ == "__main__":
    unittest.main()
