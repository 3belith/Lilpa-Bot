from __future__ import annotations

import os
import time
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
    keys = [
        key.strip()
        for key in api_keys
        if key and key.strip() and not key.strip().lower().startswith("your_")
    ]
    return list(dict.fromkeys(keys))


def load_system_prompt(path: str | os.PathLike[str] | None = None) -> str:
    file_path = Path(path) if path is not None else BASE_DIR / "personality.txt"
    if not file_path.exists():
        raise FileNotFoundError(f"Personality file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


class LilpaAI:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.system_prompt = load_system_prompt()
        self.api_keys = get_api_keys()

        if not self.api_keys:
            raise RuntimeError(
                ".env에 실제 GEMINI_API_KEY_1~6 중 하나를 설정하세요."
            )

        self._key_index = 0
        self._config = types.GenerateContentConfig(
            system_instruction=self.system_prompt
        )

    def _get_client(self):
        client = genai.Client(api_key=self.api_keys[self._key_index])
        self._key_index = (self._key_index + 1) % len(self.api_keys)
        return client

    def _is_daily_quota_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return (
            "generate_content_free_tier_requests" in message
            or "perdayperprojectpermodel" in message
            or "per day per project per model" in message
        )

    def _generate(self, prompt: str, config: types.GenerateContentConfig) -> str:
        last_error: Exception | None = None

        for attempt in range(len(self.api_keys)):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except Exception as exc:
                last_error = exc
                if (
                    not self._is_daily_quota_error(exc)
                    and ("429" in str(exc) or "resource exhausted" in str(exc).lower())
                ):
                    time.sleep(min(2 ** attempt, 8))

        if last_error is not None:
            if self._is_daily_quota_error(last_error):
                raise RuntimeError(
                    "Gemini 무료 요금제의 오늘 요청 한도(20회)를 모두 사용했어."
                ) from last_error
            if "429" in str(last_error) or "resource exhausted" in str(last_error).lower():
                raise RuntimeError(
                    "Gemini 요청 한도(429)에 도달했어. 잠시 후 다시 시도해줘."
                ) from last_error
            raise RuntimeError(f"Gemini 응답 실패: {last_error}")
        raise RuntimeError("Gemini 응답 실패: 사용 가능한 API 키가 없습니다.")

    def generate(self, prompt: str) -> str:
        return self._generate(prompt, self._config) or "엄..."

    def generate_summary(self, items: list[dict[str, object]]) -> str:
        lines: list[str] = []
        for item in items:
            lines.append(f'사용자: {item["user"]}')
            lines.append(f'릴파: {item["assistant"]}')
        conversation = "\n".join(lines)

        prompt = (
            "다음 대화에서 앞으로 기억할 가치가 있는 사실과 주제만 보존해 짧게 요약해.\n"
            "사용자가 직접 말한 중요한 정보는 보존하고, 사소한 잡담은 제거해.\n"
            "릴파의 말투, 문체, 말버릇, 답변 길이와 문장 구조는 기억하지 마.\n"
            "ㅋㅋㅋ, 감탄사, 이모지 등의 스타일 정보도 저장하지 마.\n"
            "새로운 사실을 추측하거나 만들지 말고, 최대 80단어로 요약 결과만 반환해.\n\n"
            "[대화]\n"
            f"{conversation}"
        )
        return " ".join(
            self._generate(prompt, types.GenerateContentConfig()).split()[:80]
        )
