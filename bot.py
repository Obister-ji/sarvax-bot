import discord
from discord.ext import commands
from discord import app_commands, ui
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import aiohttp
from io import BytesIO
from PIL import Image
import pytesseract

# Load environment variables
load_dotenv()

# Initialize Gemini with correct model names
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Get the correct model names dynamically
    models = [m.name for m in genai.list_models()]
    
    # Use the first available text model
    text_model_name = next((m for m in models if 'model' in m and 'text' in m.lower()), None)
    if not text_model_name:
        raise ValueError("No text generation model found")
    
    # Use the first available vision model
    vision_model_name = next((m for m in models if 'model' in m and 'vision' in m.lower()), None)
    
    text_model = genai.GenerativeModel(text_model_name)
    vision_model = genai.GenerativeModel(vision_model_name) if vision_model_name else None
    
    print(f"Using text model: {text_model_name}")
    print(f"Using vision model: {vision_model_name or 'None'}")
    
except Exception as e:
    print(f"Failed to initialize Gemini: {e}")
    exit(1)

# Persistent View Class
class PersistentAIView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="🔍 More Details",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent:more_details"
    )
    async def more_details(self, interaction: discord.Interaction, button: ui.Button):
        try:
            follow_up = text_model.generate_content(
                f"Expand on this in 3 bullet points: {interaction.message.embeds[0].description}"
            )
            embed = discord.Embed(
                title="🔍 Detailed Breakdown",
                description=follow_up.text,
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @ui.button(
        label="🗑️ Delete",
        style=discord.ButtonStyle.red,
        custom_id="persistent:delete"
    )
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("Message deleted.", ephemeral=True)

# Bot setup
class NexusAI(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="n!",
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your commands 👀"
            )
        )

    async def setup_hook(self):
        self.add_view(PersistentAIView())

bot = NexusAI()

# Core Commands
@bot.tree.command(name="ask", description="Ask NexusAI anything")
@app_commands.describe(question="Your question for the AI")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    
    try:
        response = text_model.generate_content(
            f"Respond concisely but helpfully to a Discord user: {question}"
        )
        
        embed = discord.Embed(
            title=f"🧠 NexusAI Response",
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

@bot.tree.command(name="analyze", description="Analyze an image")
async def analyze(interaction: discord.Interaction):
    if not interaction.message.attachments:
        return await interaction.response.send_message("Please attach an image!", ephemeral=True)
    
    if not vision_model:
        return await interaction.response.send_message("Image analysis is not available", ephemeral=True)
    
    await interaction.response.defer()
    attachment = interaction.message.attachments[0]
    
    try:
        if not attachment.content_type.startswith('image/'):
            return await interaction.followup.send("Only images are supported for analysis", ephemeral=True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("Failed to download image", ephemeral=True)
                
                image_data = await resp.read()
                image_part = {
                    "mime_type": attachment.content_type,
                    "data": image_data
                }
                
                response = vision_model.generate_content(
                    ["Analyze this image in detail for a Discord user. Describe:", image_part]
                )
                
                embed = discord.Embed(
                    title="🖼️ Image Analysis",
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
    print(f"✨ {bot.user} is ready!")

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))