from __future__ import annotations

import asyncio
import errno
import logging
import os
import random
import sys
import time
from pathlib import Path

import discord
from dotenv import load_dotenv

from ai import LilpaAI
from memory import ConversationMemory


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN이 없습니다.")


intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)
ai = LilpaAI()
memory = ConversationMemory(maxlen=10, recent_turns=4)
cooldowns: dict[int, float] = {}
processing_messages: set[int] = set()
summary_tasks: set[asyncio.Task[None]] = set()
summary_locks: dict[int, asyncio.Lock] = {}
MAX_GEMINI_CONCURRENCY = int(os.getenv("GEMINI_MAX_CONCURRENCY", "4"))
gemini_semaphore = asyncio.Semaphore(MAX_GEMINI_CONCURRENCY)
COOLDOWN_SECONDS = 1.0
MAX_CHARS = 2000
MAX_PROMPT_WORDS = 180
logger = logging.getLogger(__name__)

EMPTY_MESSAGES = [
    "왜 불렀어?",
    "할 말 있어?",
    "듣고 있어.",
    "말해 봐.",
    "부른 거 아니었어?",
]


def is_cooldown(user_id: int) -> bool:
    now = time.time()
    last = cooldowns.get(user_id, 0.0)
    if now - last < COOLDOWN_SECONDS:
        return True

    cooldowns[user_id] = now
    return False


def get_question(message: discord.Message) -> str:
    if bot.user is None:
        return message.content.strip()

    return (
        message.content
        .replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    )


def make_prompt(channel_id: int, username: str, question: str) -> str:
    context = memory.build_context(channel_id, max_words=MAX_PROMPT_WORDS)
    return (
        "[현재 대화 상대]\n"
        f"이름: {username}\n\n"
        "[최근 대화 맥락]\n"
        f"{context}\n\n"
        "[현재 메시지]\n"
        f"{username}: {question}"
    )


async def update_summary(channel_id: int) -> None:
    lock = summary_locks.setdefault(channel_id, asyncio.Lock())
    async with lock:
        items = memory.get_summary_request(channel_id)
        if not items:
            return

        try:
            async with gemini_semaphore:
                summary = await asyncio.to_thread(ai.generate_summary, items)
        except Exception:
            logger.exception("Conversation summary failed for channel %s", channel_id)
            summary = None
        memory.complete_summary(channel_id, summary, items)


def schedule_summary(channel_id: int) -> None:
    task = asyncio.create_task(update_summary(channel_id))
    summary_tasks.add(task)
    task.add_done_callback(summary_tasks.discard)


def chunk_text(text: str, size: int = MAX_CHARS) -> list[str]:
    return [text[index:index + size] for index in range(0, len(text), size)]


async def send_answer(message: discord.Message, text: str) -> None:
    prefix = f"{message.author.mention}\n"
    first_limit = MAX_CHARS - len(prefix)

    if len(text) <= first_limit:
        await message.reply(f"{prefix}{text}", mention_author=False)
        return

    first_part = text[:first_limit]
    await message.reply(f"{prefix}{first_part}", mention_author=False)

    remaining = text[first_limit:]
    for part in chunk_text(remaining, MAX_CHARS):
        await message.channel.send(part)


@bot.event
async def on_ready() -> None:
    print(f"{bot.user} 실행 완료")


@bot.event
async def on_error(event: str, *args: object, **kwargs: object) -> None:
    error = sys.exc_info()[1]
    if isinstance(error, OSError) and error.errno == errno.ENOENT:
        return

    logger.exception("Discord event failed: %s", event)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if bot.user not in message.mentions:
        return

    if message.id in processing_messages:
        return
    processing_messages.add(message.id)

    if is_cooldown(message.author.id):
        try:
            await message.reply("ㄱㄷ", mention_author=False)
        finally:
            processing_messages.discard(message.id)
        return

    question = get_question(message)
    if not question:
        try:
            await message.reply(
                f"{message.author.mention} {random.choice(EMPTY_MESSAGES)}",
                mention_author=False,
            )
        finally:
            processing_messages.discard(message.id)
        return

    try:
        username = message.author.display_name
        channel_id = message.channel.id
        prompt = make_prompt(channel_id, username, question)

        async with message.channel.typing():
            async with gemini_semaphore:
                answer = await asyncio.to_thread(ai.generate, prompt)

        if answer.startswith("<MOD>"):
            warning = answer[len("<MOD>"):].strip()

            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

            await message.channel.send(f"{message.author.mention} {warning}")
            return

        memory.append(channel_id, username, question, answer)
        await send_answer(message, answer)
        schedule_summary(channel_id)
    except Exception as exc:
        await message.reply(f"오류: {exc}", mention_author=False)
    finally:
        processing_messages.discard(message.id)


def run_bot() -> None:
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    run_bot()
