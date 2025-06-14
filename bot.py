import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
import sqlite3
import datetime
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------- DATABASE SETUP --------------------
ticket_conn = sqlite3.connect("tickets.db")
ticket_cursor = ticket_conn.cursor()
ticket_cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        task_heading TEXT,
        description TEXT,
        deadline TEXT,
        assignee TEXT,
        priority TEXT,
        status TEXT,
        created_at TEXT,
        completed_at TEXT
    )
''')
ticket_conn.commit()

time_conn = sqlite3.connect("work_tracker.db")
time_cursor = time_conn.cursor()
time_cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        start_time TEXT,
        end_time TEXT,
        duration TEXT,
        token TEXT
    )
''')
time_conn.commit()

# -------------------- TICKET MODAL --------------------
class TicketModal(Modal, title="📝 Work Ticket Submission"):
    task_heading = TextInput(label="Task Heading", placeholder="Enter task title")
    description = TextInput(label="Description", style=discord.TextStyle.paragraph)
    deadline = TextInput(label="Deadline (YYYY-MM-DD)")
    assignee = TextInput(label="Assignee (mention user or name)")
    priority = TextInput(label="Priority (Low/Medium/High)")

    async def on_submit(self, interaction: discord.Interaction):
        created_at = datetime.datetime.now().isoformat()
        ticket_cursor.execute("INSERT INTO tickets (user_id, task_heading, description, deadline, assignee, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(interaction.user.id), self.task_heading.value, self.description.value, self.deadline.value, self.assignee.value, self.priority.value, "Open", created_at))
        ticket_conn.commit()

        embed = discord.Embed(title=f"🧾 New Work Ticket: {self.task_heading.value}", color=0xa15a00)
        embed.add_field(name="📝 Description", value=self.description.value, inline=False)
        embed.add_field(name="📅 Deadline", value=self.deadline.value)
        embed.add_field(name="👤 Assignee", value=self.assignee.value)
        embed.add_field(name="📊 Priority", value=self.priority.value)
        embed.add_field(name="🕒 Created By", value=interaction.user.mention)
        embed.set_footer(text="SARVAX Pvt Ltd | Ticket System", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.timestamp = datetime.datetime.utcnow()

        # Create ticket thread
        ticket_channel = interaction.channel
        thread = await ticket_channel.create_thread(name=f"🛠️ {self.task_heading.value}", type=discord.ChannelType.public_thread)
        await thread.send(embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"✅ Your ticket has been created in thread {thread.mention}", ephemeral=True)

class TicketActionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="✅ Start Task", style=discord.ButtonStyle.success, custom_id="start_task"))
        self.add_item(Button(label="📦 Mark Done", style=discord.ButtonStyle.primary, custom_id="complete_task"))
        self.add_item(Button(label="❌ Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_task"))

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

@tree.command(name="workticket", description="Create a new work ticket")
async def workticket(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketModal())

@tree.command(name="workreport", description="Get your work time report")
@app_commands.describe(period="Choose 'daily' or 'weekly'")
async def workreport(interaction: discord.Interaction, period: str):
    user_id = str(interaction.user.id)
    now = datetime.datetime.now()
    if period == "daily":
        since = now - datetime.timedelta(days=1)
    elif period == "weekly":
        since = now - datetime.timedelta(weeks=1)
    else:
        await interaction.response.send_message("❌ Invalid period. Choose 'daily' or 'weekly'.")
        return

    time_cursor.execute("SELECT * FROM work_sessions WHERE user_id = ? AND start_time >= ?", (user_id, since.isoformat()))
    sessions = time_cursor.fetchall()

    total_duration = datetime.timedelta()
    for session in sessions:
        duration = datetime.timedelta(seconds=float(session[4]))
        total_duration += duration

    await interaction.response.send_message(f"🕒 Total {period.capitalize()} Work Duration: {total_duration}", ephemeral=True)

@tree.command(name="help", description="Show bot commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 SARVAX BOT COMMANDS", color=0xf4a261)
    embed.add_field(name="/workticket", value="Create a new work ticket", inline=False)
    embed.add_field(name="/workreport [daily|weekly]", value="Get your work hours", inline=False)
    embed.add_field(name="/gentoken", value="(Managers only) Generate a manual token", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="gentoken", description="Generate work token (manager only)")
@app_commands.checks.has_permissions(administrator=True)
async def gentoken(interaction: discord.Interaction, user: discord.User):
    now = datetime.datetime.now()
    token = f"SARVAX-{user.id}-{int(now.timestamp())}"
    time_cursor.execute("INSERT INTO work_sessions (user_id, start_time, end_time, duration, token) VALUES (?, ?, ?, ?, ?)",
        (str(user.id), now.isoformat(), now.isoformat(), "0", token))
    time_conn.commit()
    await interaction.response.send_message(f"✅ Token generated for {user.mention}: `{token}`", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is None and after.channel is not None:
        member._start_time = datetime.datetime.now()
    elif before.channel is not None and after.channel is None:
        end_time = datetime.datetime.now()
        start_time = getattr(member, '_start_time', end_time)
        duration = (end_time - start_time).total_seconds()
        token = f"AUTO-{member.id}-{int(end_time.timestamp())}"

        time_cursor.execute("INSERT INTO work_sessions (user_id, start_time, end_time, duration, token) VALUES (?, ?, ?, ?, ?)",
            (str(member.id), start_time.isoformat(), end_time.isoformat(), str(duration), token))
        time_conn.commit()

        try:
            await member.send(f"🕒 Work session recorded: {str(datetime.timedelta(seconds=duration))}\nToken: `{token}`")
        except:
            pass

# -------------------- RUN --------------------
if __name__ == "__main__":
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not DISCORD_BOT_TOKEN:
        raise ValueError("❌ DISCORD_BOT_TOKEN environment variable not set.")
    bot.run(DISCORD_BOT_TOKEN)
