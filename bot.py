import discord
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, View, Button
import os
from datetime import datetime, timedelta

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory storage for simplicity
TICKETS = []
USER_TIMES = {}
TOKENS = []

# ---------------------- TICKET MODAL ----------------------
class TicketModal(Modal, title="📋 Create a Work Ticket"):
    task_heading = TextInput(label="Task Heading", placeholder="Enter a clear title", required=True)
    task_description = TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    assignee = TextInput(label="Assignee Discord Tag", placeholder="@username", required=True)
    deadline = TextInput(label="Deadline (YYYY-MM-DD)", placeholder="2025-06-20", required=True)
    priority = TextInput(label="Priority (Low/Medium/High)", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        ticket = {
            "heading": self.task_heading.value,
            "description": self.task_description.value,
            "assignee": self.assignee.value,
            "deadline": self.deadline.value,
            "priority": self.priority.value,
            "created_by": interaction.user.name,
            "timestamp": datetime.now()
        }
        TICKETS.append(ticket)
        embed = discord.Embed(title=f"✅ New Ticket Created: {ticket['heading']}", color=0x00ff00)
        embed.add_field(name="📝 Description", value=ticket['description'], inline=False)
        embed.add_field(name="👤 Assignee", value=ticket['assignee'], inline=True)
        embed.add_field(name="⏳ Deadline", value=ticket['deadline'], inline=True)
        embed.add_field(name="⚡ Priority", value=ticket['priority'], inline=True)
        embed.set_footer(text=f"Created by {interaction.user.name} | SARVAX")
        await interaction.response.send_message(embed=embed, ephemeral=False)

# ---------------------- CREATE TICKET COMMAND ----------------------
@bot.tree.command(name="create_ticket", description="Create a task ticket")
async def create_ticket(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketModal())

# ---------------------- TIME TRACKER ----------------------
@bot.event
async def on_voice_state_update(member, before, after):
    now = datetime.now()
    if before.channel is None and after.channel is not None:
        USER_TIMES[member.id] = now
    elif before.channel is not None and after.channel is None:
        start_time = USER_TIMES.pop(member.id, now)
        duration = now - start_time
        print(f"{member.name} spent {duration} in VC")

# ---------------------- REPORT COMMAND ----------------------
@bot.tree.command(name="report", description="Generate work report")
async def report(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 SARVAX Work Report", color=0x3498db)
    if TICKETS:
        for t in TICKETS[-5:]:
            embed.add_field(
                name=f"{t['heading']} ({t['priority']})",
                value=f"👤 {t['assignee']} | ⏳ {t['deadline']}\n📝 {t['description'][:100]}...",
                inline=False
            )
    else:
        embed.description = "No tickets yet."
    await interaction.response.send_message(embed=embed)

# ---------------------- TOKEN GENERATOR ----------------------
@bot.tree.command(name="generate_token", description="Generate task tokens (Admin only)")
@commands.has_permissions(administrator=True)
async def generate_token(interaction: discord.Interaction):
    token = f"SARVAX-{len(TOKENS)+1}-{datetime.now().strftime('%H%M')}"
    TOKENS.append(token)
    await interaction.response.send_message(f"🔐 Token generated: `{token}`", ephemeral=True)

# ---------------------- BOT SETUP ----------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"🤖 Logged in as {bot.user}")

# ---------------------- START BOT ----------------------
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        print("❌ Bot token not set. Use export DISCORD_BOT_TOKEN='your-token'")
    else:
        bot.run(TOKEN)
