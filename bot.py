import os
import discord
from discord.ext import commands
from openai import OpenAI

# Load API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY is not set. Please add it to Railway.")

# Setup OpenAI Client
client_ai = OpenAI(api_key=OPENAI_API_KEY)

# Discord Bot Setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

@bot.command(name="ask")
async def ask(ctx, *, prompt):
    try:
        response = client_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        await ctx.send(response.choices[0].message.content)
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

# Start the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
