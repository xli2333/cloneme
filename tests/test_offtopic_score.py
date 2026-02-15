from __future__ import annotations

import unittest

from app.services.generation import GenerationService


class OfftopicScoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GenerationService()

    def test_on_topic_should_score_lower_than_off_topic(self) -> None:
        frame = {
            "focus_terms": ["电影", "今天", "要不要"],
            "question_like": True,
        }
        user_msg = "今天要不要看电影？"
        on_topic = ["可以呀，今天就看电影。"]
        off_topic = ["我突然想吃火锅，先不聊这个。"]

        on_score = self.service._offtopic_score(user_msg, on_topic, frame)
        off_score = self.service._offtopic_score(user_msg, off_topic, frame)

        self.assertLess(on_score, off_score)
        self.assertGreaterEqual(off_score, 0.0)
        self.assertLessEqual(off_score, 1.0)

    def test_soft_penalty_range(self) -> None:
        frame = {"focus_terms": ["项目", "验收"], "question_like": False}
        mid_topic = ["项目我看了，先把验收项拆一下。"]
        score = self.service._offtopic_score("我们先做项目验收", mid_topic, frame)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_activity_query_status_reply_should_not_be_max_penalty(self) -> None:
        frame = {"focus_terms": ["你在干嘛呢"], "question_like": True}
        reply = ["我还在改图呢，刚忙完一点。"]
        score = self.service._offtopic_score("你在干嘛呢", reply, frame, relevance_hint=0.75)
        self.assertLess(score, 0.76)

    def test_echo_reply_should_have_low_flow_and_higher_echo_penalty(self) -> None:
        frame = {"focus_terms": ["火鸡面"], "question_like": False, "status_update": True}
        good = ["哇火鸡面这么早就吃呀，辣不辣？"]
        echo = ["哈哈哈哈哈", "火鸡面火鸡面～"]
        good_flow = self.service._conversation_flow_score("我在吃火鸡面~", good, frame)
        echo_flow = self.service._conversation_flow_score("我在吃火鸡面~", echo, frame)
        good_pen = self.service._echo_penalty("我在吃火鸡面~", good)
        echo_pen = self.service._echo_penalty("我在吃火鸡面~", echo)
        self.assertGreater(good_flow, echo_flow)
        self.assertGreater(echo_pen, good_pen)

    def test_laugh_expression_should_not_be_penalized_as_echo(self) -> None:
        laugh_only = ["哈哈哈哈哈"]
        normal = ["我在呢"]
        laugh_pen = self.service._echo_penalty("你在干嘛呢", laugh_only)
        normal_pen = self.service._echo_penalty("你在干嘛呢", normal)
        self.assertLessEqual(laugh_pen, normal_pen)


if __name__ == "__main__":
    unittest.main()
