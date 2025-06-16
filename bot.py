import discord
from discord.ext import commands
from discord import app_commands
import os
import openai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# Bot Setup
class NexusAI(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced!")

bot = NexusAI()

# Event: on_ready
@bot.event
async def on_ready():
    print(f"✨ Logged in as {bot.user} (ID: {bot.user.id})")

# Slash Command: /ask
@bot.tree.command(name="ask", description="Ask OpenAI a question")
@app_commands.describe(prompt="What do you want to ask?")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        answer = response.choices[0].message.content.strip()

        embed = discord.Embed(
            title="🧠 NexusAI Response",
            description=answer,
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Asked by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error: {str(e)}",
            ephemeral=True
        )

# Run Bot
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
