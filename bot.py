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

# Initialize Gemini Pro
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
text_model = genai.GenerativeModel('gemini-pro')
vision_model = genai.GenerativeModel('gemini-pro-vision')

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
        self.persistent_views_added = False

bot = NexusAI()

# Custom UI Components
class AIResponseView(ui.View):
    def __init__(self, query, response):
        super().__init__(timeout=120)
        self.query = query
        self.response = response

    @ui.button(label="🔍 More Details", style=discord.ButtonStyle.blurple)
    async def more_details(self, interaction: discord.Interaction, button: ui.Button):
        follow_up = text_model.generate_content(
            f"Expand on this in 3 bullet points: {self.response.text}"
        )
        embed = discord.Embed(
            title="🔍 Detailed Breakdown",
            description=follow_up.text,
            color=0x00ff00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🗑️ Delete", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()

# Core Commands
@bot.tree.command(name="ask", description="Ask NexusAI anything")
@app_commands.describe(question="Your question for the AI")
async def ask(interaction: discord.Interaction, question: str):
    """Premium AI response with rich embed"""
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
        
        view = AIResponseView(question, response)
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"```{str(e)}```",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="analyze", description="Analyze an image or document")
async def analyze(interaction: discord.Interaction):
    """Advanced image/text analysis"""
    if not interaction.message.attachments:
        embed = discord.Embed(
            title="❌ Missing Attachment",
            description="Please attach an image or document!",
            color=0xff0000
        )
        return await interaction.response.send_message(embed=embed)
    
    await interaction.response.defer()
    attachment = interaction.message.attachments[0]
    
    try:
        if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    img_data = await resp.read()
            
            response = vision_model.generate_content([
                "Analyze this image in detail for a Discord user. Include:",
                "1. Key visual elements",
                "2. Any readable text",
                "3. Interesting details",
                {"mime_type": attachment.content_type, "data": img_data}
            ])
            
            embed = discord.Embed(
                title="🖼️ Image Analysis",
                description=response.text,
                color=0x00ffff
            )
            
        else:  # Document processing
            text = pytesseract.image_to_string(Image.open(BytesIO(await attachment.read())))
            summary = text_model.generate_content(
                f"Summarize this document in 3 key points:\n\n{text[:10000]}"
            )
            
            embed = discord.Embed(
                title="📄 Document Summary",
                description=summary.text,
                color=0x7289da
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

# Premium Features
class PremiumModal(ui.Modal, title="🔒 Premium Chat"):
    message = ui.TextInput(label="Your private message to NexusAI")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        response = text_model.generate_content(
            f"Respond to this private user message: {self.message.value}"
        )
        
        embed = discord.Embed(
            title="🔒 Premium AI Response",
            description=response.text,
            color=0xffd700
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="private", description="Start a premium private chat")
async def private_chat(interaction: discord.Interaction):
    """Exclusive 1-on-1 AI chat"""
    await interaction.response.send_modal(PremiumModal())

# Bot Events
@bot.event
async def on_ready():
    if not bot.persistent_views_added:
        bot.add_view(AIResponseView("", ""))  # Persistent view
        bot.persistent_views_added = True
    
    await bot.tree.sync()
    print(f"✨ {bot.user} is ready with premium features!")

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
