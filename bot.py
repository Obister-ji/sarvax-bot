import discord
from discord.ext import commands
import openai
import os

# Set up your OpenAI API key here
openai.api_key = os.getenv("OPENAI_API_KEY")  # Store this as an environment variable for safety

# Intents and Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Event: Bot is Ready
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Command: AI Chat using OpenAI GPT-3.5
@bot.command()
async def ask(ctx, *, question):
    await ctx.send("🤖 Thinking...")
    try:
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ]
        )
        answer = response.choices[0].message.content
        await ctx.send(answer)
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

# Run the bot with your token
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
