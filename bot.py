import discord
from discord.ext import commands
from discord import app_commands
import openai
import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Set up Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Event: on_ready
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"✅ Bot is online as {bot.user}")

# Slash command: /ask
@bot.tree.command(name="ask", description="Ask OpenAI a question")
@app_commands.describe(prompt="Your question to the AI")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo"

            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content
        await interaction.followup.send(f"💬 **AI says:**\n{reply}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# Run bot
bot.run(DISCORD_TOKEN)
