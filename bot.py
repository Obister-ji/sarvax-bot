import os
import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Embed, ButtonStyle
from discord.ui import Modal, TextInput, View, Button
import sqlite3
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Connect to SQLite
conn = sqlite3.connect('sarvax.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS work_sessions (
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                heading TEXT,
                description TEXT,
                deadline TEXT,
                assignee TEXT,
                priority TEXT,
                timestamp TEXT
            )''')
conn.commit()

voice_start_times = {}

class WorkTicketModal(Modal, title="Raise a Work Ticket"):
    heading = TextInput(label="Task Heading", required=True)
    description = TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    deadline = TextInput(label="Deadline (YYYY-MM-DD)", required=True)
    assignee = TextInput(label="Assignee (mention @user)", required=True)
    priority = TextInput(label="Priority (High/Medium/Low)", required=True)

    async def on_submit(self, interaction: Interaction):
        embed = Embed(title="📌 Work Ticket Raised!", color=0xffa500)
        embed.add_field(name="📝 Heading", value=self.heading.value, inline=False)
        embed.add_field(name="📄 Description", value=self.description.value, inline=False)
        embed.add_field(name="📅 Deadline", value=self.deadline.value, inline=True)
        embed.add_field(name="👤 Assignee", value=self.assignee.value, inline=True)
        embed.add_field(name="🚦 Priority", value=self.priority.value, inline=True)
        embed.set_footer(text=f"Raised by {interaction.user.display_name}")

        thread = await interaction.channel.create_thread(name=f"Ticket - {self.heading.value}", type=discord.ChannelType.public_thread)
        await thread.send(embed=embed, view=TicketActions())

        with conn:
            conn.execute("INSERT INTO tickets (user_id, heading, description, deadline, assignee, priority, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (interaction.user.id, self.heading.value, self.description.value, self.deadline.value, self.assignee.value, self.priority.value, datetime.now().isoformat()))

        await interaction.response.send_message("✅ Ticket raised successfully! Check the new thread.", ephemeral=True)

class TicketActions(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="✅ Complete", style=ButtonStyle.success, custom_id="complete_ticket"))
        self.add_item(Button(label="❌ Cancel", style=ButtonStyle.danger, custom_id="cancel_ticket"))

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot is online as {bot.user}!")

@tree.command(name="workticket", description="Raise a new work ticket")
async def workticket(interaction: Interaction):
    await interaction.response.send_modal(WorkTicketModal())

@tree.command(name="workreport", description="Get your work report")
@app_commands.describe(scope="Choose daily or weekly report")
@app_commands.choices(scope=[app_commands.Choice(name="daily", value="daily"), app_commands.Choice(name="weekly", value="weekly")])
async def workreport(interaction: Interaction, scope: app_commands.Choice[str]):
    user_id = interaction.user.id
    with conn:
        rows = conn.execute("SELECT start_time, end_time FROM work_sessions WHERE user_id = ?", (user_id,)).fetchall()
    total_seconds = 0
    for start, end in rows:
        if end:
            start_time = datetime.fromisoformat(start)
            end_time = datetime.fromisoformat(end)
            total_seconds += (end_time - start_time).total_seconds()
    hours = total_seconds / 3600
    await interaction.response.send_message(f"🕒 You worked {hours:.2f} hours in total ({scope.name}).")

@tree.command(name="help", description="Show all commands")
async def help_command(interaction: Interaction):
    embed = Embed(title="🛠️ SARVAX Bot Commands", color=0x00bfff)
    embed.add_field(name="/workticket", value="Raise a new work ticket.", inline=False)
    embed.add_field(name="/workreport", value="Show your work hours report.", inline=False)
    embed.add_field(name="/help", value="Show this help message.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        voice_start_times[member.id] = datetime.now()
    elif before.channel is not None and after.channel is None:
        start_time = voice_start_times.pop(member.id, None)
        if start_time:
            with conn:
                conn.execute("INSERT INTO work_sessions (user_id, start_time, end_time) VALUES (?, ?, ?)",
                             (member.id, start_time.isoformat(), datetime.now().isoformat()))

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
