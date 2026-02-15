from __future__ import annotations

import unittest

from app.services.generation import GenerationService


class _FakeResult:
    def __init__(self, text: str, model_used: str = "fake-model") -> None:
        self.text = text
        self.model_used = model_used


class _FakeClient:
    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, **_: object) -> _FakeResult:
        return _FakeResult(self._text)


class RepairPassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GenerationService()

    def test_repair_candidate_should_return_fixed_bubbles(self) -> None:
        client = _FakeClient('{"bubbles": ["好，我们就按电影这个话题说。"], "reason": "拉回语境"}')
        result = self.service._repair_candidate(
            user_message="今天要不要看电影？",
            context={"frame": {"focus_terms": ["电影"]}, "persona": {}},
            bubbles=["我突然想聊别的。"],
            client=client,
        )
        self.assertIsNotNone(result)
        repaired, reason = result or ([], "")
        self.assertTrue(repaired)
        self.assertIn("电影", "".join(repaired))
        self.assertTrue(reason)

    def test_repair_candidate_invalid_payload_should_return_none(self) -> None:
        client = _FakeClient("not-json")
        result = self.service._repair_candidate(
            user_message="今天要不要看电影？",
            context={"frame": {"focus_terms": ["电影"]}, "persona": {}},
            bubbles=["我突然想聊别的。"],
            client=client,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
