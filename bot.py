import discord
from discord import app_commands
from discord.ext import commands
import openai
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        synced = await tree.sync()
        print(f'🔁 Synced {len(synced)} command(s).')
    except Exception as e:
        print(f'❌ Sync failed: {e}')

@tree.command(name="ask", description="Ask the AI a question")
@app_commands.describe(prompt="What do you want to ask?")
async def ask(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()  # 👈 tells Discord you need more time
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or gpt-4 if you have access
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content
        await interaction.followup.send(reply)  # 👈 follow-up with real response
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# Run the bot with your token
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
