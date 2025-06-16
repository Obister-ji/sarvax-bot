import discord
from discord.ext import commands
from openai import OpenAI
import os

# Get API keys from environment variables
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Set up OpenAI client (new SDK style)
client = OpenAI(api_key=OPENAI_API_KEY)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

# Slash command: /ask
@bot.tree.command(name="ask", description="Ask a question to AI")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()  # Show thinking status

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ]
        )
        reply = response.choices[0].message.content
        await interaction.followup.send(reply)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# Start the bot
bot.run(DISCORD_TOKEN)
