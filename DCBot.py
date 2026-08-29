import os
import asyncio
import random
from collections import defaultdict, deque
from time import time

import discord
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

with open(
    "personality.txt",
    "r",
    encoding="utf-8"
) as f:
    SYSTEM_PROMPT = f.read()


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

api_keys = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
    os.getenv("GEMINI_API_KEY_6"),
]

api_keys = [
    key for key in api_keys
    if key
]

if not api_keys:
    raise RuntimeError("Gemini API key가 하나도 없습니다.")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN이 없습니다.")


key_index = 0

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# 채널별 최근 대화 기억
# 서로 다른 사용자가 말해도 같은 채널이면 맥락을 이어서 볼 수 있음.
history = defaultdict(
    lambda: deque(maxlen=8)
)

cooldowns = {}
COOLDOWN = 1

EMPTY_MESSAGES = [
    "왜 불렀어?",
    "할 말 있어?",
    "듣고 있어.",
    "말해 봐.",
    "부른 거 아니었어?"
]


def get_ai():
    global key_index

    client = genai.Client(
        api_key=api_keys[key_index]
    )

    key_index = (
        key_index + 1
    ) % len(api_keys)

    return client


def is_cooldown(user_id):
    now = time()
    last = cooldowns.get(user_id, 0)

    if now - last < COOLDOWN:
        return True

    cooldowns[user_id] = now
    return False


def get_question(message):
    return (
        message.content
        .replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    )


def make_prompt(channel_id, username, question):
    recent = history[channel_id]

    if recent:
        context_lines = []

        for item in recent:
            context_lines.append(
                f'{item["username"]}: {item["user"]}'
            )
            context_lines.append(
                f'릴파: {item["assistant"]}'
            )

        context = "\n".join(context_lines)
    else:
        context = "(아직 최근 대화 없음)"

    return f"""
[현재 대화 상대]
이름: {username}

[최근 대화 맥락]
{context}

[현재 메시지]
{username}: {question}
""".strip()


def ask_ai(prompt):
    for _ in range(len(api_keys)):
        try:
            client = get_ai()

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                )
            )

            return response.text or "엄..."

        except Exception as e:
            print(f"Gemini 오류: {e}")
            continue

    return "엄.."


async def send_answer(message, text):
    prefix = f"{message.author.mention}\n"

    # 첫 메시지는 멘션 길이까지 포함해서 Discord 2000자 제한 계산
    first_limit = 2000 - len(prefix)

    if len(text) <= first_limit:
        await message.reply(
            f"{prefix}{text}",
            mention_author=False
        )
        return

    first_part = text[:first_limit]

    await message.reply(
        f"{prefix}{first_part}",
        mention_author=False
    )

    remaining = text[first_limit:]

    parts = [
        remaining[i:i + 2000]
        for i in range(0, len(remaining), 2000)
    ]

    for part in parts:
        await message.channel.send(part)


def save_history(
    channel_id,
    username,
    question,
    answer
):
    history[channel_id].append({
        "username": username,
        "user": question,
        "assistant": answer
    })


@bot.event
async def on_ready():
    print(f"{bot.user} 실행 완료")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user not in message.mentions:
        return

    if is_cooldown(message.author.id):
        await message.reply(
            "ㄱㄷ",
            mention_author=False
        )
        return

    question = get_question(message)

    if not question:
        await message.reply(
            f"{message.author.mention} "
            f"{random.choice(EMPTY_MESSAGES)}",
            mention_author=False
        )
        return

    try:
        # Discord 서버 닉네임 우선
        username = message.author.display_name
        channel_id = message.channel.id

        prompt = make_prompt(
            channel_id,
            username,
            question
        )

        async with message.channel.typing():
            # Gemini의 동기 호출이 Discord event loop를 막지 않게 처리
            answer = await asyncio.to_thread(
                ask_ai,
                prompt
            )

        # MOD 처리
        if answer.startswith("<MOD>"):
            warning = answer[len("<MOD>"):].strip()

            # MOD 대화도 기억시킴.
            # 다음 메시지에서 "아까 그 말..." 식으로 이어갈 수 있음.
            save_history(
                channel_id,
                username,
                question,
                warning
            )

            # 원래 사용자가 보낸 메시지 삭제
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            except discord.NotFound:
                pass

            # MOD 뒤의 문구만 출력
            await message.channel.send(
                f"{message.author.mention} {warning}"
            )
            return

        save_history(
            channel_id,
            username,
            question,
            answer
        )

        await send_answer(
            message,
            answer
        )

    except Exception as e:
        await message.reply(
            f"오류: {e}",
            mention_author=False
        )


bot.run(DISCORD_TOKEN)
