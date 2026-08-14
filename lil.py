import os
import discord
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

with open("prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# 사용자별 직전 대화 저장
conversation_history = {}


@bot.event
async def on_ready():
    print(f"{bot.user} 실행 완료")


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if bot.user not in message.mentions:
        return

    question = message.content.replace(
        f"<@{bot.user.id}>", ""
    ).replace(
        f"<@!{bot.user.id}>", ""
    ).strip()

    if not question:
        return

    user_id = message.author.id

    previous = conversation_history.get(
        user_id,
        {"user": "", "assistant": ""}
    )

    prompt = f"""
이전 사용자 메시지:
{previous['user']}

이전 AI 답변:
{previous['assistant']}

현재 사용자 메시지:
{question}
"""

    await message.channel.typing()

    try:
        response = client.responses.create(
            model="gpt-5",
            input=prompt
        )

        answer = response.output_text

        conversation_history[user_id] = {
            "user": question,
            "assistant": answer
        }

        if len(answer) > 2000:
            answer = answer[:1990] + "..."

        await message.reply(
            answer,
            mention_author=False
        )

    except Exception as e:
        await message.reply(
            f"오류: {e}",
            mention_author=False
        )


bot.run(os.getenv("DISCORD_TOKEN"))
