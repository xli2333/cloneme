from __future__ import annotations

import unittest

from app.config import settings
from app.services.generation import GenerationService
from app.services.persona_routing import resolve_persona_key_from_user_id


class WecomPersonaRoutingTests(unittest.TestCase):
    def test_user_id_with_dxa_should_use_dxa_persona(self) -> None:
        self.assertEqual(resolve_persona_key_from_user_id("Dxa_Main_User"), settings.dxa_persona_key)

    def test_user_id_without_dxa_should_use_friends_persona(self) -> None:
        self.assertEqual(resolve_persona_key_from_user_id("yucheng_wang"), settings.friends_persona_key)

    def test_fallback_lines_for_friends_should_not_use_strict_nickname(self) -> None:
        svc = GenerationService()
        persona = {
            "core_persona": {
                "relationship": {
                    "strict_nickname": "",
                    "forbidden_nicknames": ["宝贝", "宝宝"],
                }
            },
            "adaptive_persona": {},
        }
        lines = svc._fallback_lines(
            "今晚吃什么",
            frame={},
            persona=persona,
            persona_key=settings.friends_persona_key,
        )
        joined = "".join(lines)
        self.assertNotIn("宝贝", joined)
        self.assertIn("我在", joined)


if __name__ == "__main__":
    unittest.main()

