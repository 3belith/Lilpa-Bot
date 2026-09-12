import unittest

from memory import ConversationMemory


class TestConversationMemory(unittest.TestCase):
    def test_build_context_summarizes_when_history_is_too_long(self):
        memory = ConversationMemory(maxlen=10)

        for i in range(12):
            memory.append(
                "channel-1",
                "user",
                f"question {i} " + ("word " * 30),
                f"answer {i} " + ("word " * 30),
            )

        summary_called = {"value": False}

        def fake_summary(items):
            summary_called["value"] = True
            return "짧은 요약"

        context = memory.build_context(
            "channel-1",
            max_words=120,
            summary_callback=fake_summary,
        )

        self.assertIn("짧은 요약", context)
        self.assertTrue(summary_called["value"])

    def test_long_term_summary_and_context_stay_bounded(self):
        memory = ConversationMemory(maxlen=4)

        for i in range(100):
            memory.append("channel-1", "user", f"question {i} " * 20, "answer " * 20)

        context = memory.build_context("channel-1", max_words=60)

        self.assertLessEqual(len(memory._summaries["channel-1"].split()), 80)
        self.assertLessEqual(len(context.split()), 60)


if __name__ == "__main__":
    unittest.main()
