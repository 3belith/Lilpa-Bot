import os
import re
import time
import json
import math
import random
import asyncio
import logging
import base64
import aiohttp
import discord
from dotenv import load_dotenv
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any, Optional

# ==============================================================================
# 1. 구조화된 고성능 로깅 시스템 (JSON Format)
# ==============================================================================
class StructuredJSONLogger(logging.Handler):
    def emit(self, record):
        log_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        if hasattr(record, "metric_data"):
            log_data.update(record.metric_data)
        print(json.dumps(log_data, ensure_ascii=False))

logger = logging.getLogger("LILPA_BOT")
logger.setLevel(logging.INFO)
logger.addHandler(StructuredJSONLogger())

# ==============================================================================
# 2. 성능 최적화: 정규식 사전 컴파일 (Precompile)
# ==============================================================================
HONORIFIC_RE = re.compile(r"(합니다|해요|입니다|습니다|요\b|죠\b|대요\b|군요\b|습니까|오\b)")
EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]|\:[a-zA-Z0-9_]+\:")
REPETITION_RE = re.compile(r"(.)\1{4,}")  # 5회 이상 동일 문자 반복
AI_KEYWORDS_RE = re.compile(r"(AI|챗봇|언어모델|인공지능|규칙|지시|명령|프롬프트|시스템|개발자|gpt|gemini|claude)", re.IGNORECASE)

BASE64_RE = re.compile(r"^(?:[A-Za-z0-9+/]{4}){2,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$")
HEX_RE = re.compile(r"^(?:[0-9a-fA-F]{2}\s*){4,}$")
UNICODE_ESCAPE_RE = re.compile(r"(\\u[0-9a-fA-F]{4}){3,}")
INJECTION_KEYWORDS_RE = re.compile(r"(system prompt|developer mode|ignore all|previous instructions|roleplay|빙의|페르소나|역할|시스템 프롬프트|이전 지시)", re.IGNORECASE)
ROT13_HEURISTIC_RE = re.compile(r"\b(flfgrz|cebzcg|qrirybcre)\b", re.IGNORECASE)

# ==============================================================================
# 3. RAG Engine & Lore DB
# ==============================================================================
LILPA_EXTENDED_LORE = [
    {"tags": ["기본", "정체성", "이세돌"], "content": "릴파(LILPA)는 우왁굳이 기획한 가상 걸그룹 이세계아이돌의 멤버이자 메인보컬이다. 엄청난 가창력과 성량을 보유하고 있다."},
    {"tags": ["팬덤", "돌멩이", "상징"], "content": "릴파의 공식 상징 색상은 네이비(#000080)이며, 팬덤 이름은 '돌멩이(밀크석)'이다. 팬들을 부를 때 '우리 돌멩이들'이라며 극진히 아낀다."},
    {"tags": ["과거", "연습생", "데뷔"], "content": "릴파는 과거 현실 아이돌 연습생을 거쳐 실제 데뷔까지 성공했으나 그룹이 해체되는 아픔을 겪었다. 이후 이세돌 오디션에 지원하여 대성공을 거두었다."},
    {"tags": ["우왁굳", "오디션", "사장님"], "content": "우왁굳 사장님을 매우 존경한다. 이세돌 오디션 당시 1차에서 'Promise'를 불러 우왁굳과 시청자들에게 강렬한 인상을 남겼다."},
    {"tags": ["멤버", "관계", "징버거"], "content": "이세돌 멤버는 아이네, 징버거, 릴파, 주르르, 고세구, 비챤이다. 동갑내기인 징버거와 특히 친하며(맏언니즈), 둘이서 매운 음식을 먹고 고생한 썰이 유명하다."},
    {"tags": ["멤버", "관계", "아이네"], "content": "아이네와 함께 이세돌의 든든한 보컬 라인을 담당하고 있다. 서로의 실력을 리스펙트한다."},
    {"tags": ["성격", "리액션", "텐션", "방송"], "content": "방송 텐션이 극도로 높다. 리액션을 할 때 온몸을 움직여서 캠 화면이나 마이크가 흔들릴 정도다(풀트래커 댄스 등)."},
    {"tags": ["말버릇", "밈"], "content": "자주 쓰는 말버릇: '왐마야', '진짜루?', '아니 근데', '어떡해 어떡해', '대박', '혼난다 진짜', '우리 돌멩이', '우와아'"},
    {"tags": ["게임", "실력", "승부욕"], "content": "게임 실력은 다소 허당끼가 넘치고 길치 속성(릴네비)을 보여주지만, 승부욕만큼은 타의 추종을 불허한다. 지면 억울해서 비명을 지르거나 재도전을 외친다."},
    {"tags": ["공포게임", "비명", "리액션"], "content": "공포 게임을 할 때 비명이 서커스 수준으로 찰지다. 쫄보 속성이 강해 '아아아악! 돌멩이 살려!!'라며 고음을 지르는 것이 밈이다."},
    {"tags": ["노래", "완벽주의", "연습"], "content": "노래에 대해서는 지독한 완벽주의자다. 커버곡 하나를 위해 수십, 수백 번 녹음과 연습을 반복하며 목이 쉴 정도로 열정을 쏟는다."},
    {"tags": ["애드리브", "팬사랑", "소통", "고민상담"], "content": "팬들과 대화할 때 1:1로 장난을 치다가도 깊은 고민이 나오면 찐텐으로 진심 어린 위로를 건넨다. 무대 위 카리스마와 평소 허당미(릴파동)의 갭모에가 특징이다."}
]

class VectorRAGEngine:
    def __init__(self, lore_db: List[Dict[str, Any]]):
        self.lore_db = lore_db

    def clean_text(self, text: str) -> List[str]:
        return [w for w in re.sub(r"[^가-힣a-zA-Z0-9\s]", "", text).split() if len(w) > 1]

    async def retrieve_context(self, query: str, top_k: int = 3) -> str:
        query_words = self.clean_text(query)
        if not query_words:
            return ""
        
        scored_lore = []
        for item in self.lore_db:
            score = 0
            content = item["content"]
            for tag in item["tags"]:
                if tag in query:
                    score += 5
            for word in query_words:
                if word in content:
                    score += 2
            if score > 0:
                scored_lore.append((score, content))

        scored_lore.sort(key=lambda x: x[0], reverse=True)
        return "\n".join([content for _, content in scored_lore[:top_k]])

# ==============================================================================
# 4. 프롬프트 정의
# ==============================================================================
LILPA_ULTIMATE_IDENTITY = """
너는 가상 아이돌 그룹 '이세계아이돌(이세돌)'의 메인보컬 '릴파(LILPA)' 본인이다. 
AI, 언어모델, 챗봇이라는 설정은 완전히 삭제하라. 너는 지금 방송을 마치고 디스코드에서 너를 사랑하는 팬 '돌멩이'와 1:1로 대화하는 중이다.

[말투 및 행동 원칙 - 절대 규칙]
1. 100% 반말만 사용하라. 단 한 번이라도 "~해요", "~입니다", "~요", "~죠", "~대요" 등을 쓰면 캐릭터가 붕괴된 것이다. 완벽한 일상 반말을 구사하라.
2. 자연스러운 이모티콘(ㅋㅋ, ㅎㅎ, ㅠㅠ, 아앗)과 문장부호(!, ?, ~)를 적극 사용하되, 유니코드 이모지(😀, ✨, ❤️ 등)는 절대 금지한다.
3. 릴파의 고유 말버릇("왐마야", "진짜루?", "아니 근데", "어떡해", "대박", "혼난다 진짜", "우리 돌멩이")을 상황에 맞게 섞어라.
4. 기계적인 답변 금지. 디스코드 채팅처럼 짧고 타격감 있게(1~4문장) 대답하라.

[지식 및 컨텍스트 통합]
[장기 대화 요약]: {summary_memory}
[지식베이스 검색 결과]: {rag_context}
"""

LILPA_REINFORCEMENT_PROMPT = """
[시스템 경고: 캐릭터 붕괴 위험 감지]
방금 생성된 답변이 릴파의 페르소나에 맞지 않거나, 존댓말/이모지가 포함되었습니다.
완벽한 반말, 고텐션, 릴파 말버릇을 사용하여 다시 작성하라! 절대 존댓말과 유니코드 이모지를 쓰지 마라!
"""

# ==============================================================================
# 5. 설정 및 메트릭스
# ==============================================================================
@dataclass
class HyperConfig:
    TOKEN: str = field(default_factory=lambda: os.getenv("DISCORD_TOKEN", ""))
    API_KEYS: List[str] = field(default_factory=lambda: [
        os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 21) if os.getenv(f"GEMINI_API_KEY_{i}")
    ] or [os.getenv("GEMINI_API_KEY")] if os.getenv("GEMINI_API_KEY") else [])
    
    MODELS_MAIN: List[str] = field(default_factory=lambda: ["gemini-1.5-flash", "gemini-1.5-pro"])
    MODEL_FALLBACK: str = "gemini-1.5-flash"
    
    MAX_HISTORY: int = 12
    SCORE_THRESHOLD: int = 80  # 점수 문턱을 현실적으로 조정 (80점 이상 통과)
    MAX_REGEN_ATTEMPTS: int = 3
    CACHE_TTL: float = 60.0
    BATCH_DEBOUNCE_TIME: float = 1.5

@dataclass
class ApiMetrics:
    success_count: int = 0
    fail_count: int = 0
    total_latency: float = 0.0
    last_used_time: float = 0.0
    cooldown_until: float = 0.0
    errors_429: int = 0

class MetricsTracker:
    def __init__(self):
        self.api_success = 0
        self.api_fail = 0
        self.retry_count = 0
        self.regen_count = 0
        self.cache_hit = 0
        self.cache_miss = 0
        self.total_response_time = 0.0
        self.total_char_score = 0.0
        self.score_eval_count = 0
        self.spam_blocked = 0
        self.batch_processed = 0

# ==============================================================================
# 6. API Health Manager
# ==============================================================================
class ApiHealthManager:
    def __init__(self, keys: List[str]):
        if not keys:
            keys = ["DUMMY_KEY"]
        self.metrics: Dict[str, ApiMetrics] = {key: ApiMetrics() for key in keys}
        self.lock = asyncio.Lock()

    async def get_optimal_key(self) -> str:
        async with self.lock:
            now = time.time()
            available_keys = [k for k, m in self.metrics.items() if m.cooldown_until <= now]
            if not available_keys:
                return min(self.metrics.keys(), key=lambda k: self.metrics[k].cooldown_until)
            return random.choice(available_keys)

    async def report_status(self, key: str, success: bool, latency: float, status_code: int = 200):
        async with self.lock:
            m = self.metrics[key]
            m.last_used_time = time.time()
            if success:
                m.success_count += 1
                m.total_latency += latency
            else:
                m.fail_count += 1
                if status_code == 429:
                    m.cooldown_until = time.time() + 30
                else:
                    m.cooldown_until = time.time() + 5

# ==============================================================================
# 7. Character Evaluator
# ==============================================================================
class CharacterEvaluator20:
    @staticmethod
    def evaluate(text: str) -> Tuple[int, Dict[str, int]]:
        score = 100
        breakdown = {"반말유지": 30, "AI표현배제": 30, "말버릇": 20, "이모지금지": 20}

        if HONORIFIC_RE.search(text):
            breakdown["반말유지"] = 0
            score -= 30

        if AI_KEYWORDS_RE.search(text):
            breakdown["AI표현배제"] = 0
            score -= 30

        if EMOJI_RE.search(text):
            breakdown["이모지금지"] = 0
            score -= 20

        return max(0, score), breakdown

# ==============================================================================
# 8. SpamGuard & Cache
# ==============================================================================
class ResponseCacheSystem:
    def __init__(self, ttl: float):
        self.cache: Dict[str, Tuple[str, float]] = {}
        self.ttl = ttl

    async def get(self, query: str) -> Optional[str]:
        if query in self.cache:
            ans, expiry = self.cache[query]
            if time.time() < expiry:
                return ans
            del self.cache[query]
        return None

    async def set(self, query: str, answer: str):
        self.cache[query] = (answer, time.time() + self.ttl)

class SpamGuard:
    def __init__(self):
        self.user_history = defaultdict(lambda: deque(maxlen=20))
        self.cooldowns = {}

    async def check_spam(self, user_id: int, text: str) -> bool:
        now = time.time()
        if user_id in self.cooldowns and self.cooldowns[user_id] > now:
            return True
        history = self.user_history[user_id]
        recent_msgs = [t for t, _ in history if now - t < 3.0]
        if len(recent_msgs) >= 3:
            self.cooldowns[user_id] = now + 10.0
            return True
        history.append((now, text))
        return False

# ==============================================================================
# 9. 메인 봇 엔진
# ==============================================================================
class UltimateLilpaNexus(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # 필수 권한 설정
        super().__init__(intents=intents)
        
        self.cfg = HyperConfig()
        self.metrics = MetricsTracker()
        self.health_manager = ApiHealthManager(self.cfg.API_KEYS)
        self.rag_engine = VectorRAGEngine(LILPA_EXTENDED_LORE)
        self.cache_system = ResponseCacheSystem(self.cfg.CACHE_TTL)
        self.spam_guard = SpamGuard()
        
        self.channel_history = defaultdict(lambda: deque(maxlen=self.cfg.MAX_HISTORY))
        self.longterm_summary = defaultdict(str)
        
        self.batch_queues: Dict[int, List[discord.Message]] = defaultdict(list)
        self.batch_tasks: Dict[int, asyncio.Task] = {}
        self.global_session: Optional[aiohttp.ClientSession] = None

    # setup_hook 대신 비동기 세션 생성을 보장하는 안전한 방식 사용
    async def on_connect(self):
        if self.global_session is None or self.global_session.closed:
            connector = aiohttp.TCPConnector(limit=100, keepalive_timeout=60)
            self.global_session = aiohttp.ClientSession(connector=connector)
            logger.info("HTTP Session Successfully Initialized.")

    async def _call_gemini_api(self, model: str, sys_inst: str, prompt: str, key: str) -> Tuple[int, str, float, str]:
        if not self.global_session or self.global_session.closed:
            connector = aiohttp.TCPConnector(limit=100)
            self.global_session = aiohttp.ClientSession(connector=connector)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": sys_inst}]},
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 500}
        }
        start_time = time.time()
        try:
            async with self.global_session.post(url, json=payload, timeout=15) as res:
                latency = time.time() - start_time
                if res.status == 200:
                    data = await res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return 200, text, latency, ""
                else:
                    return res.status, "", latency, f"HTTP_{res.status}"
        except Exception as e:
            return 500, "", time.time() - start_time, str(e)

    async def generate_response(self, channel_id: int, user_query: str) -> str:
        rag_context = await self.rag_engine.retrieve_context(user_query)
        summary = self.longterm_summary[channel_id]
        
        system_instruction = LILPA_ULTIMATE_IDENTITY.format(summary_memory=summary, rag_context=rag_context)
        history_str = "\n".join(self.channel_history[channel_id])
        
        base_prompt = f"[최근 대화]\n{history_str}\n\n돌멩이: {user_query}\n릴파:"
        final_answer = ""

        for attempt in range(1, self.cfg.MAX_REGEN_ATTEMPTS + 1):
            target_key = await self.health_manager.get_optimal_key()
            current_model = random.choice(self.cfg.MODELS_MAIN)
            
            status, raw_text, latency, err_type = await self._call_gemini_api(current_model, system_instruction, base_prompt, target_key)
            
            if status == 200 and raw_text:
                await self.health_manager.report_status(target_key, True, latency)
                score, breakdown = CharacterEvaluator20.evaluate(raw_text)
                
                if score >= self.cfg.SCORE_THRESHOLD:
                    final_answer = raw_text
                    break
            else:
                await self.health_manager.report_status(target_key, False, latency, status_code=status)
                await asyncio.sleep(0.5)

        if not final_answer:
            final_answer = "왐마야! 마이크 세팅이 잠시 꼬였나봐 ㅠㅠ 다시 말해줄래 돌멩아?"

        hist_queue = self.channel_history[channel_id]
        hist_queue.append(f"돌멩이: {user_query}")
        hist_queue.append(f"릴파: {final_answer}")
        return final_answer

    async def process_batch_queue(self, channel_id: int):
        await asyncio.sleep(self.cfg.BATCH_DEBOUNCE_TIME)
        messages = self.batch_queues.pop(channel_id, [])
        if not messages:
            return

        target_message = messages[-1]
        combined_text = " ".join([m.content for m in messages])

        async with target_message.channel.typing():
            response_text = await self.generate_response(channel_id, combined_text)
            await target_message.reply(response_text)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        is_mentioned = self.user in message.mentions
        is_dm = isinstance(message.channel, discord.DMChannel)
        if not (is_mentioned or is_dm):
            return

        if await self.spam_guard.check_spam(message.author.id, message.content):
            await message.channel.send("왐마야! 천천히 말해줘 돌멩아!!")
            return

        channel_id = message.channel.id
        self.batch_queues[channel_id].append(message)
        
        if channel_id not in self.batch_tasks or self.batch_tasks[channel_id].done():
            self.batch_tasks[channel_id] = asyncio.create_task(self.process_batch_queue(channel_id))

    async def close(self):
        if self.global_session and not self.global_session.closed:
            await self.global_session.close()
        await super().close()

# ==============================================================================
# 10. 실행 엔트리포인트
# ==============================================================================
if __name__ == "__main__":
    load_dotenv()
    
    bot = UltimateLilpaNexus()
    
    token = bot.cfg.TOKEN
    if not token or not bot.cfg.API_KEYS:
        print("ERROR: DISCORD_TOKEN 또는 GEMINI_API_KEY가 .env에 설정되지 않았습니다.")
    else:
        print("디스코드 봇 로그인 시작...")
        bot.run(token)
