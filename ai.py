from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def get_api_keys() -> list[str]:
    api_keys = [
        os.getenv(f"GEMINI_API_KEY_{index}")
        for index in range(1, 7)
    ]
    return [key for key in api_keys if key]


def load_system_prompt(path: str | os.PathLike[str] | None = None) -> str:
    file_path = Path(path) if path is not None else BASE_DIR / "personality.txt"
    if not file_path.exists():
        raise FileNotFoundError(f"Personality file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


class LilpaAI:
    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        self.model = model
        self.system_prompt = load_system_prompt()
        self.api_keys = get_api_keys()

        if not self.api_keys:
            raise RuntimeError("Gemini API key가 하나도 없습니다.")

        self._key_index = 0
        self._config = types.GenerateContentConfig(
            system_instruction=self.system_prompt
        )

    def _get_client(self):
        client = genai.Client(api_key=self.api_keys[self._key_index])
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return client

    def generate(self, prompt: str) -> str:
        last_error: Exception | None = None

        for _ in range(len(self.api_keys)):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=self._config,
                )
                return response.text or "엄..."
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise RuntimeError(f"Gemini 응답 실패: {last_error}")
        raise RuntimeError("Gemini 응답 실패: 사용 가능한 API 키가 없습니다.")
