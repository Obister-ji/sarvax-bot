import discord
import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Load API keys
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!ask"):
        prompt = message.content[len("!ask "):]

        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",  # or gpt-4 if you have access
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            reply = response.choices[0].message.content
            await message.channel.send(reply)

        except Exception as e:
            await message.channel.send("❌ Error occurred while generating response.")
            print(e)

client.run(DISCORD_TOKEN)
