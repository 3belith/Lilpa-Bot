import unittest

from memory import ConversationMemory


class TestConversationMemory(unittest.TestCase):
    def test_summary_is_not_requested_before_ten_turns(self):
        memory = ConversationMemory(maxlen=10, recent_turns=4)

        for index in range(9):
            memory.append("channel-1", "user", f"question {index}", f"answer {index}")

        self.assertIsNone(memory.get_summary_request("channel-1"))

    def test_summary_request_keeps_six_old_turns_and_four_recent_turns(self):
        memory = ConversationMemory(maxlen=10, recent_turns=4)

        for index in range(10):
            memory.append("channel-1", "user", f"question {index}", f"answer {index}")

        request = memory.get_summary_request("channel-1")

        self.assertIsNotNone(request)
        self.assertEqual(
            [item["user"] for item in request],
            [f"question {index}" for index in range(6)],
        )
        memory.complete_summary("channel-1", "사용자는 파이썬을 공부한다.")
        self.assertEqual(len(memory.get_recent("channel-1")), 4)
        self.assertIn("사용자는 파이썬을 공부한다.", memory.build_context("channel-1"))

    def test_summary_failure_preserves_recent_turns(self):
        memory = ConversationMemory(maxlen=10, recent_turns=4)

        for index in range(10):
            memory.append("channel-1", "user", f"question {index}", f"answer {index}")

        memory.complete_summary("channel-1", None)

        self.assertEqual(
            [item["user"] for item in memory.get_recent("channel-1")],
            [f"question {index}" for index in range(6, 10)],
        )

    def test_context_budget_prefers_latest_turns(self):
        memory = ConversationMemory(maxlen=10, recent_turns=4)

        for index in range(10):
            memory.append(
                "channel-1", "user", f"question {index} " * 20, f"answer {index} " * 20
            )
        memory.complete_summary("channel-1", "짧은 요약")

        context = memory.build_context("channel-1", max_words=60)

        self.assertLessEqual(len(context.split()), 60)
        self.assertIn("question 9", context)


if __name__ == "__main__":
    unittest.main()
