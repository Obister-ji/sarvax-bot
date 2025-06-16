import discord
import openai
import os

# 🔐 Load your keys
DISCORD_BOT_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 🤖 OpenAI Model Configuration
MODEL_NAME = "gpt-4o"  # or "gpt-3.5-turbo" if you prefer

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # 🔹 Trigger command (customize as needed)
    if message.content.startswith("!ask "):
        prompt = message.content[5:].strip()
        if not prompt:
            await message.channel.send("❓ Please provide a prompt.")
            return

        await message.channel.send("🤖 Thinking...")

        try:
            # 🧠 Call OpenAI
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful and witty assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            reply = response.choices[0].message.content
            await message.channel.send(reply)

        except openai.error.OpenAIError as e:
            await message.channel.send(f"❌ OpenAI Error: {str(e)}")

client.run(DISCORD_BOT_TOKEN)
