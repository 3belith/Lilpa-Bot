from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable


class ConversationMemory:
    def __init__(self, maxlen: int = 10, recent_turns: int = 4) -> None:
        self._history: defaultdict[Any, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=maxlen)
        )
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
        self._history[channel_id].append(
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
            return "(아직 최근 대화 없음)"

        lines: list[str] = []
        for item in recent:
            lines.append(f'{item["username"]}: {item["user"]}')
            lines.append(f'릴파: {item["assistant"]}')

        text = "\n".join(lines)
        if len(text.split()) <= max_words:
            return text

        if summary_callback is None:
            summary_callback = self._default_summary

        older_items = recent[:-self.recent_turns] if len(recent) > self.recent_turns else []
        recent_items = recent[-self.recent_turns:]

        summary = summary_callback(older_items) if older_items else "최근 대화 시작"
        recent_lines: list[str] = []
        for item in recent_items:
            recent_lines.append(f'{item["username"]}: {item["user"]}')
            recent_lines.append(f'릴파: {item["assistant"]}')

        recent_text = "\n".join(recent_lines)
        return f"{self.summary_prefix}{summary}\n\n[최근 대화]\n{recent_text}"

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
