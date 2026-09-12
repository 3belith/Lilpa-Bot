from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable


class ConversationMemory:
    def __init__(self, maxlen: int = 10, recent_turns: int = 4) -> None:
        self._history: defaultdict[Any, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )
        self._summaries: defaultdict[Any, str] = defaultdict(str)
        self.max_summary_words = 80
        self.recent_turns = recent_turns
        self.summary_prefix = "[이전 대화 요약]\n"

    def append(
        self,
        channel_id: Any,
        username: str,
        question: str,
        answer: str,
        *,
        is_moderation: bool = False,
    ) -> None:
        history = self._history[channel_id]
        if len(history) == history.maxlen:
            evicted = history[0]
            self._summaries[channel_id] = self._merge_summary(
                self._summaries[channel_id],
                self._default_summary([evicted]),
            )

        history.append(
            {
                "username": username,
                "user": question,
                "assistant": answer,
                "is_moderation": is_moderation,
            }
        )

    def _visible_items(self, channel_id: Any) -> list[dict[str, Any]]:
        return [
            item
            for item in list(self._history[channel_id])
            if not item.get("is_moderation", False)
        ]

    def build_context(
        self,
        channel_id: Any,
        max_words: int = 180,
        summary_callback: Callable[[list[dict[str, Any]]], str] | None = None,
    ) -> str:
        recent = self._visible_items(channel_id)
        if not recent:
            summary = self._summaries[channel_id]
            return f"{self.summary_prefix}{summary}" if summary else "(아직 최근 대화 없음)"

        lines: list[str] = []
        for item in recent:
            lines.append(f'{item["username"]}: {item["user"]}')
            lines.append(f'릴파: {item["assistant"]}')

        text = "\n".join(lines)
        stored_summary = self._summaries[channel_id]
        if len(text.split()) <= max_words and not stored_summary:
            return text

        if summary_callback is None:
            summary_callback = self._default_summary

        older_items = recent[:-self.recent_turns] if len(recent) > self.recent_turns else []
        recent_items = recent[-self.recent_turns:]

        new_summary = summary_callback(older_items) if older_items else "최근 대화 시작"
        summary = self._merge_summary(stored_summary, new_summary)
        self._summaries[channel_id] = summary
        recent_lines: list[str] = []
        for item in recent_items:
            recent_lines.append(f'{item["username"]}: {item["user"]}')
            recent_lines.append(f'릴파: {item["assistant"]}')

        recent_text = "\n".join(recent_lines)
        prefix_words = len(self.summary_prefix.split())
        section_words = len("[최근 대화]".split())
        summary = self._trim_words(
            summary,
            max(1, max_words - prefix_words - section_words - 1),
        )
        summary_text = f"{self.summary_prefix}{summary}"
        fixed_words = len(summary_text.split()) + section_words
        recent_text = self._trim_words(
            recent_text,
            max(1, max_words - fixed_words),
        )
        return f"{summary_text}\n\n[최근 대화]\n{recent_text}"

    def _merge_summary(self, previous: str, latest: str) -> str:
        words = f"{previous} {latest}".split()
        if len(words) > self.max_summary_words:
            words = words[-self.max_summary_words:]
        return " ".join(words)

    def _trim_words(self, text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[-max_words:])

    def _default_summary(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "최근 대화 시작."

        summary_parts: list[str] = []
        for item in items:
            summary_parts.append(f"{item['username']}: {item['user']}")
            summary_parts.append(f"릴파: {item['assistant']}")

        summary_text = " ".join(summary_parts)
        words = summary_text.split()
        if len(words) > 40:
            words = words[:40]
        trimmed = " ".join(words)
        return f"{trimmed}..." if len(summary_text.split()) > 40 else trimmed

    def get_recent(self, channel_id: Any) -> list[dict[str, Any]]:
        return self._visible_items(channel_id)
