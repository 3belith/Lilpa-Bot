import os

import discord
from dotenv import load_dotenv
from google import genai


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

history = {}

with open("prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

def get_question(message):

    return (
        message.content
        .replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    )


def make_prompt(user_id, question):

    previous = history.get(
        user_id,
        {"user": "", "assistant": ""}
    )

    return f"""
{SYSTEM_PROMPT}

이전 사용자 메시지:
{previous["user"]}

이전 AI 답변:
{previous["assistant"]}

현재 사용자 메시지:
{question}
"""


def ask_ai(prompt):

    response = ai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


def save_history(user_id, question, answer):

    history[user_id] = {
        "user": question,
        "assistant": answer
    }


@bot.event
async def on_ready():

    print(f"{bot.user} 실행 완료")


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if bot.user not in message.mentions:
        return

    question = get_question(message)

    if not question:
        return

    await message.channel.typing()

    try:

        prompt = make_prompt(
            message.author.id,
            question
        )

        answer = ask_ai(prompt)

        save_history(
            message.author.id,
            question,
            answer
        )

        await message.reply(
            answer[:2000],
            mention_author=False
        )

    except Exception as e:

        await message.reply(
            f"오류: {e}",
            mention_author=False
        )


bot.run(DISCORD_TOKEN)
