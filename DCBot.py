import os
import discord
from dotenv import load_dotenv
from google import genai
from time import time
import random

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
    os.getenv("GEMINI_API_KEY_6")
]
api_keys = [
    key for key in api_keys
    if key
]
key_index = 0
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
history = {}
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
    for _ in range(len(api_keys)):
        try:
            client = get_ai()
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text or "엄..."
        except Exception:
            continue
    return "엄.."



async def send_answer(message, text):
    parts = [
        text[i:i + 2000]
        for i in range(0, len(text), 2000)
    ]
    for index, part in enumerate(parts):
        if index == 0:
            await message.reply(
                f"{message.author.mention}\n{part}",
                mention_author=False
            )
        else:
            await message.channel.send(part)



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
    if is_cooldown(message.author.id):
        await message.reply("ㄱㄷ")
        return
        
    question = get_question(message)
    
    if not question:
        await message.reply(
            f"{message.author.mention} {random.choice(EMPTY_MESSAGES)}",
            mention_author=False
        )    
        return
        
    async with message.channel.typing():
        answer = ask_ai(prompt)
    
    try:
        prompt = make_prompt(
            message.author.id,
            question
        )
        answer = ask_ai(prompt)
        
        if answer.startswith("<MOD>"):
            warning = answer.replace(
                "<MOD>",
                ""
            ).strip()

            await message.delete()
            await message.channel.send(
                f"{message.author.mention} {warning}"
            )
            return

        save_history(
            message.author.id,
            question,
            answer
        )
        await send_answer(message, answer)
    except Exception as e:
        await message.reply(
            f"오류: {e}",
            mention_author=False
        )



bot.run(DISCORD_TOKEN)
