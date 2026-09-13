from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class ConversationMemory:
    def __init__(self, maxlen: int = 10, recent_turns: int = 4) -> None:
        if maxlen < 1 or recent_turns < 1:
            raise ValueError("maxlen and recent_turns must be positive")

        self._history: defaultdict[Any, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )
        self._summaries: defaultdict[Any, str] = defaultdict(str)
        self._summary_pending: set[Any] = set()
        self.max_summary_words = 80
        self.recent_turns = min(recent_turns, maxlen)
        self.summary_prefix = "[이전 대화 요약]"

    def append(
        self,
        channel_id: Any,
        username: str,
        question: str,
        answer: str,
    ) -> None:
        history = self._history[channel_id]
        history.append(
            {
                "username": username,
                "user": question,
                "assistant": answer,
            }
        )

        if len(history) == history.maxlen:
            self._summary_pending.add(channel_id)

    def _visible_items(self, channel_id: Any) -> list[dict[str, Any]]:
        return list(self._history[channel_id])

    def build_context(
        self,
        channel_id: Any,
        max_words: int = 180,
    ) -> str:
        if max_words <= 0:
            return ""

        recent = self._visible_items(channel_id)[-self.recent_turns:]
        recent_lines: list[str] = []
        for item in reversed(recent):
            turn = [
                f'{item["username"]}: {item["user"]}',
                f'릴파: {item["assistant"]}',
            ]
            candidate = turn + recent_lines
            if len("\n".join(["[최근 대화]"] + candidate).split()) > max_words:
                if not recent_lines:
                    available_words = max(0, max_words - 2)
                    recent_lines = [" ".join(" ".join(turn).split()[:available_words])]
                break
            recent_lines = candidate

        lines = ["[최근 대화]", *recent_lines] if recent_lines else []
        summary = self._summaries[channel_id]
        if summary:
            remaining_words = max_words - len("\n".join(lines).split()) - 2
            if remaining_words > 0:
                lines = [
                    self.summary_prefix,
                    " ".join(summary.split()[:remaining_words]),
                    *lines,
                ]
        return "\n".join(lines) if lines else "(아직 최근 대화 없음)"

    def get_summary_request(self, channel_id: Any) -> list[dict[str, Any]] | None:
        if channel_id not in self._summary_pending:
            return None

        visible = self._visible_items(channel_id)
        older = visible[:-self.recent_turns]
        return older or None

    def complete_summary(
        self,
        channel_id: Any,
        summary: str | None,
        summarized_items: list[dict[str, Any]] | None = None,
    ) -> None:
        if channel_id not in self._summary_pending:
            return

        history = self._history[channel_id]
        if summary:
            self._summaries[channel_id] = self._merge_summary(
                self._summaries[channel_id], summary
            )

        if summarized_items:
            for item in summarized_items:
                try:
                    history.remove(item)
                except ValueError:
                    continue

        while len(history) > self.recent_turns:
            history.popleft()
        self._summary_pending.discard(channel_id)

    def _merge_summary(self, previous: str, latest: str) -> str:
        previous_sentences = [
            part.strip() for part in previous.split(". ") if part.strip()
        ]
        latest_sentences = [
            part.strip() for part in latest.split(". ") if part.strip()
        ]
        merged: list[str] = []
        for sentence in previous_sentences + latest_sentences:
            if sentence and sentence not in merged:
                merged.append(sentence)
        words = " ".join(merged).split()
        return " ".join(words[-self.max_summary_words:])

    def get_recent(self, channel_id: Any) -> list[dict[str, Any]]:
        return self._visible_items(channel_id)
