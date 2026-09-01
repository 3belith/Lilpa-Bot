from __future__ import annotations

import os
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def read_personality(path: str | os.PathLike[str] | None = None) -> str:
    file_path = Path(path) if path is not None else BASE_DIR / "personality.txt"
    if not file_path.exists():
        raise FileNotFoundError(f"Personality file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


class LilpaAgent:
    """Reusable AI agent wrapper for Lilpa Bot."""

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        self.model = model
        self.system_prompt = read_personality()
        self.api_keys = [
            key
            for key in (
                os.getenv("GEMINI_API_KEY_1"),
                os.getenv("GEMINI_API_KEY_2"),
                os.getenv("GEMINI_API_KEY_3"),
                os.getenv("GEMINI_API_KEY_4"),
                os.getenv("GEMINI_API_KEY_5"),
                os.getenv("GEMINI_API_KEY_6"),
            )
            if key
        ]
        if not self.api_keys:
            raise RuntimeError("Gemini API key가 하나도 없습니다.")

        self._key_index = 0
        self.history = defaultdict(lambda: deque(maxlen=10))

    def _get_client(self):
        client = genai.Client(api_key=self.api_keys[self._key_index])
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return client

    def build_prompt(self, channel_id: str | int, username: str, question: str) -> str:
        recent = list(self.history[channel_id])
        if recent:
            context_lines: list[str] = []
            for item in recent[-4:]:
                context_lines.append(f'{item["username"]}: {item["user"]}')
                context_lines.append(f'릴파: {item["assistant"]}')
            context = "\n".join(context_lines)
        else:
            context = "(아직 최근 대화 없음)"

        return (
            "[현재 대화 상대]\n"
            f"이름: {username}\n\n"
            "[최근 대화 맥락]\n"
            f"{context}\n\n"
            "[현재 메시지]\n"
            f"{username}: {question}"
        )

    def ask(self, prompt: str) -> str:
        last_error: Exception | None = None

        for _ in range(len(self.api_keys)):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt
                    ),
                )
                return response.text or "엄..."
            except Exception as exc:  # pragma: no cover - fallback loop
                last_error = exc
                continue

        if last_error is not None:
            raise RuntimeError(f"Gemini 응답 실패: {last_error}")
        raise RuntimeError("Gemini 응답 실패: 사용 가능한 API 키가 없습니다.")

    def reply(self, channel_id: str | int, username: str, question: str) -> str:
        prompt = self.build_prompt(channel_id, username, question)
        answer = self.ask(prompt)
        self.history[channel_id].append(
            {
                "username": username,
                "user": question,
                "assistant": answer,
            }
        )
        return answer


if __name__ == "__main__":
    agent = LilpaAgent()
    while True:
        user_text = input("당신: ")
        if not user_text:
            continue
        print(f"릴파: {agent.reply('cli', '사용자', user_text)}")
