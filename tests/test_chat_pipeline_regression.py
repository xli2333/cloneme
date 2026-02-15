from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config import settings
from app.services.generation import GenerationService


class _FakeResult:
    def __init__(self, text: str, model_used: str = "fake-model") -> None:
        self.text = text
        self.model_used = model_used


class _FakeClient:
    def __init__(self, mode: str = "direct") -> None:
        self.mode = mode

    def generate(self, **kwargs: object) -> _FakeResult:
        prompt = str(kwargs.get("prompt", ""))
        if "对话规划器" in prompt:
            return _FakeResult('{"candidate_count": 10, "bubble_count": 2}')
        if "请生成" in prompt:
            if self.mode == "repair":
                return _FakeResult(
                    '{"candidates":[{"bubbles":["今天看电影先缓一缓，我们聊音乐吧。"],"strategy":"offtopic"}]}'
                )
            return _FakeResult(
                '{"candidates":[{"bubbles":["可以，今天就看电影。"],"strategy":"on_topic"},{"bubbles":["我去做饭了。"],"strategy":"off_topic"}]}'
            )
        if "风格复核器" in prompt:
            return _FakeResult('{"winner_index": 0, "reason":"ok"}')
        if "最小改写修复" in prompt:
            return _FakeResult(
                '{"bubbles":["好，那我们就按你说的电影这个点继续。"],"reason":"拉回语境"}'
            )
        return _FakeResult("ok")

    def embed_texts(self, *args: object, **kwargs: object) -> list[list[float]]:
        raise RuntimeError("force lexical fallback")


class ChatPipelineRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GenerationService()
        self.style = {"avg_len": 8, "median_len": 8, "run_avg": 2.0, "laugh_ratio": 0.1}
        self.pref = {
            "weights": {
                "semantic": 0.45,
                "style": 0.22,
                "relation": 0.12,
                "recency": 0.08,
                "online_memory": 0.13,
            },
            "tone": {"laugh_ratio_target": 0.1},
            "multi_bubble": {"default_count": 2},
        }
        self.persona = {
            "relationship": {"strict_nickname": "宝贝", "forbidden_nicknames": ["老婆", "宝宝"]},
            "speech_traits": {"avg_len": 8, "top_phrases": ["我在", "先接住你"]},
        }
        self.context = {
            "recent_block": [{"id": 1, "role": "user", "content": "今天要不要看电影？"}],
            "online_block": [{"role": "assistant", "content": "看电影也行"}],
            "style_block": ["我在", "慢慢来"],
            "segments": [],
            "frame": {"focus_terms": ["电影", "今天", "要不要"], "question_like": True},
            "persona": self.persona,
            "rag_chars": 0,
        }

    def test_generate_should_keep_on_topic_without_fallback(self) -> None:
        fake = _FakeClient(mode="direct")
        with (
            patch.object(self.service, "_load_profiles", return_value=(self.style, self.pref, self.persona)),
            patch.object(self.service, "_build_context_block", return_value=self.context),
            patch("app.services.generation.get_gemini_client", return_value=fake),
        ):
            result = self.service.generate("conv_1", "今天要不要看电影？")

        self.assertIn("电影", "".join(result.bubbles))
        self.assertNotEqual(result.debug.get("final_path"), "fallback")

    def test_generate_should_use_repair_before_fallback(self) -> None:
        fake = _FakeClient(mode="repair")
        old_low = settings.repair_threshold_low
        old_high = settings.repair_threshold_high
        try:
            settings.repair_threshold_low = 0.10
            settings.repair_threshold_high = 0.90
            with (
                patch.object(self.service, "_load_profiles", return_value=(self.style, self.pref, self.persona)),
                patch.object(self.service, "_build_context_block", return_value=self.context),
                patch("app.services.generation.get_gemini_client", return_value=fake),
            ):
                result = self.service.generate("conv_2", "今天要不要看电影？")
        finally:
            settings.repair_threshold_low = old_low
            settings.repair_threshold_high = old_high

        self.assertIn(result.debug.get("final_path"), {"repair", "direct"})
        self.assertIn("电影", "".join(result.bubbles))


if __name__ == "__main__":
    unittest.main()
