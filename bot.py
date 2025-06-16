import discord
from discord.ext import commands
from discord import app_commands, ui
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import aiohttp

# Load environment variables
load_dotenv()

# Initialize Gemini with correct model names
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Filter only models that support generateContent
    available_models = list(genai.list_models())

    text_model = next(
        (genai.GenerativeModel(m.name) for m in available_models if "generateContent" in m.supported_generation_methods and "vision" not in m.name.lower()),
        None
    )
    vision_model = next(
        (genai.GenerativeModel(m.name) for m in available_models if "generateContent" in m.supported_generation_methods and "vision" in m.name.lower()),
        None
    )

    if not text_model:
        raise RuntimeError("No supported text model found for generateContent.")

    print(f"✅ Using text model: {text_model.model_name}")
    print(f"🖼️ Using vision model: {vision_model.model_name if vision_model else 'None'}")

except Exception as e:
    print(f"❌ Failed to initialize Gemini: {e}")
    exit(1)

# Persistent Button View
class PersistentAIView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔍 More Details", style=discord.ButtonStyle.blurple, custom_id="persistent:more_details")
    async def more_details(self, interaction: discord.Interaction, button: ui.Button):
        try:
            desc = interaction.message.embeds[0].description
            follow_up = text_model.generate_content(f"Expand in 3 bullet points: {desc}")
            embed = discord.Embed(
                title="🔍 Detailed Breakdown",
                description=follow_up.text,
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red, custom_id="persistent:delete")
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("🗑️ Message deleted.", ephemeral=True)

# Custom Bot Class
class NexusAI(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="n!",
            intents=intents,
            help_command=None,
            activity=discord.Activity(type=discord.ActivityType.watching, name="your commands 👀")
        )

    async def setup_hook(self):
        self.add_view(PersistentAIView())

bot = NexusAI()

# Command: Ask AI
@bot.tree.command(name="ask", description="Ask NexusAI anything")
@app_commands.describe(question="Your question for the AI")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        response = text_model.generate_content(f"Respond concisely and helpfully: {question}")
        embed = discord.Embed(
            title="🧠 NexusAI Response",
            description=response.text,
            color=0x5865F2,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed, view=PersistentAIView())
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"```{str(e)}```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

# Command: Analyze Image
@bot.tree.command(name="analyze", description="Analyze an image (attach one before using)")
async def analyze(interaction: discord.Interaction):
    if not vision_model:
        return await interaction.response.send_message("🖼️ Image analysis model is not available.", ephemeral=True)

    if not interaction.message or not interaction.message.attachments:
        return await interaction.response.send_message("Please attach an image to your message!", ephemeral=True)

    await interaction.response.defer()
    attachment = interaction.message.attachments[0]

    try:
        if not attachment.content_type.startswith("image/"):
            return await interaction.followup.send("Only image files are supported.", ephemeral=True)

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("Failed to download image.", ephemeral=True)
                image_data = await resp.read()

        image_part = {
            "mime_type": attachment.content_type,
            "data": image_data
        }

        response = vision_model.generate_content(["Analyze this image in detail:", image_part])

        embed = discord.Embed(
            title="📷 Image Analysis",
            description=response.text,
            color=0x00ffff
        )
        embed.set_thumbnail(url=attachment.url)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Analysis Failed",
            description=f"```{str(e)}```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

# Bot Events
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 {bot.user} is online and ready!")

# Run Bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
