import discord
from discord.ext import commands
from discord.ui import Modal, InputText, View, Button
from datetime import datetime
import sqlite3
import random
import string
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Unified SQLite Setup
conn = sqlite3.connect('work_tracker.db')
cursor = conn.cursor()

# Work Sessions Table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_sessions (
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        duration INTEGER,
        work_token TEXT
    )
''')

# Ticket Table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER,
        assignee_id INTEGER,
        heading TEXT,
        description TEXT,
        deadline TEXT,
        priority TEXT,
        status TEXT,
        created_at TEXT,
        completed_at TEXT
    )
''')

conn.commit()

# Token Generator
def generate_work_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# ========================== EVENT HANDLERS ==========================

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user.name}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Employee Work Hours"))

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if before.channel is None and after.channel is not None:
        token = generate_work_token()
        cursor.execute('INSERT INTO work_sessions (user_id, start_time, work_token) VALUES (?, ?, ?)',
                       (member.id, datetime.now().isoformat(), token))
        conn.commit()
        await member.send(f"🔹 **Work Session Started**\n⏰ Time: {datetime.now().strftime('%H:%M')}\n🔑 Token: `{token}`")

    elif before.channel is not None and after.channel is None:
        cursor.execute('SELECT start_time, work_token FROM work_sessions WHERE user_id=? AND end_time IS NULL', (member.id,))
        session = cursor.fetchone()
        if session:
            start_time = datetime.fromisoformat(session[0])
            duration = (datetime.now() - start_time).total_seconds() // 60
            cursor.execute('UPDATE work_sessions SET end_time=?, duration=? WHERE user_id=? AND end_time IS NULL',
                           (datetime.now().isoformat(), int(duration), member.id))
            conn.commit()
            await member.send(f"✅ **Work Session Ended**\n⏳ Duration: {int(duration)} minutes\n🔑 Token: `{session[1]}`")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or not interaction.data.get("custom_id"):
        return

    custom_id = interaction.data["custom_id"]
    if custom_id.startswith(("start_", "done_", "cancel_")):
        ticket_id = int(custom_id.split("_")[1])
        cursor.execute("SELECT heading FROM tickets WHERE id=?", (ticket_id,))
        result = cursor.fetchone()
        if not result:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return

        action = custom_id.split("_")[0]
        if action == "start":
            new_status = "In Progress"
        elif action == "done":
            new_status = "Done"
            cursor.execute("UPDATE tickets SET completed_at=? WHERE id=?", (datetime.now().isoformat(), ticket_id))
        elif action == "cancel":
            new_status = "Canceled"
        else:
            new_status = "Pending"

        cursor.execute("UPDATE tickets SET status=? WHERE id=?", (new_status, ticket_id))
        conn.commit()
        await interaction.response.send_message(f"🔁 Ticket #{ticket_id} marked as **{new_status}**.", ephemeral=False)

# ========================== WORK TICKET MODAL ==========================

class WorkTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Create Work Ticket")
        self.add_item(InputText(label="Task Heading", placeholder="Enter a short task title", max_length=100))
        self.add_item(InputText(label="Task Description", style=discord.InputTextStyle.long, placeholder="Provide task details"))
        self.add_item(InputText(label="Deadline (e.g., 2025-06-15 17:00)", placeholder="Optional", required=False))
        self.add_item(InputText(label="Assign to (mention user ID)", placeholder="e.g., 123456789012345678"))
        self.add_item(InputText(label="Priority (High, Medium, Low)", placeholder="Choose priority"))

    async def callback(self, interaction: discord.Interaction):
        heading = self.children[0].value
        description = self.children[1].value
        deadline = self.children[2].value
        assignee_id = int(self.children[3].value)
        priority = self.children[4].value.capitalize()

        cursor.execute('''INSERT INTO tickets (creator_id, assignee_id, heading, description, deadline, priority, status, created_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (interaction.user.id, assignee_id, heading, description, deadline, priority, "Pending", datetime.now().isoformat()))
        conn.commit()
        ticket_id = cursor.lastrowid

        assignee = interaction.guild.get_member(assignee_id)
        thread_name = f"ticket-{ticket_id}-{heading.replace(' ', '-')[:20]}"
        thread = await interaction.channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)

        embed = discord.Embed(title=f"🎫 Ticket #{ticket_id}: {heading}", description=description, color=0x00b0f4)
        embed.add_field(name="👤 Assigned to", value=assignee.mention, inline=True)
        embed.add_field(name="📅 Deadline", value=deadline or "Not specified", inline=True)
        embed.add_field(name="⚙️ Priority", value=priority, inline=True)
        embed.add_field(name="📌 Status", value="🟡 Pending", inline=False)
        embed.set_footer(text=f"Created by {interaction.user.name} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        buttons = View()
        buttons.add_item(Button(label="✅ Start Task", style=discord.ButtonStyle.success, custom_id=f"start_{ticket_id}"))
        buttons.add_item(Button(label="📦 Mark as Done", style=discord.ButtonStyle.primary, custom_id=f"done_{ticket_id}"))
        buttons.add_item(Button(label="❌ Cancel Task", style=discord.ButtonStyle.danger, custom_id=f"cancel_{ticket_id}"))

        await thread.send(content=assignee.mention, embed=embed, view=buttons)
        await interaction.response.send_message(f"✅ Ticket #{ticket_id} created and assigned to {assignee.mention}", ephemeral=True)

# ========================== COMMANDS ==========================

@bot.command()
async def workticket(ctx):
    await ctx.send_modal(WorkTicketModal())

@bot.command(name="workreport")
async def work_report(ctx, period="daily"):
    if period.lower() == "daily":
        cursor.execute('SELECT SUM(duration) FROM work_sessions WHERE user_id=? AND date(start_time)=date("now")', (ctx.author.id,))
    elif period.lower() == "weekly":
        cursor.execute('SELECT SUM(duration) FROM work_sessions WHERE user_id=? AND date(start_time)>=date("now", "-7 days")', (ctx.author.id,))
    else:
        await ctx.send("❌ Invalid period. Use `daily` or `weekly`.")
        return

    total_minutes = cursor.fetchone()[0] or 0
    await ctx.send(f"📊 **Your {period} work report:**\n⏱️ Total Time: **{int(total_minutes)} minutes**")

@bot.command(name="gentoken")
@commands.has_role("Manager")
async def generate_token(ctx, user: discord.Member):
    token = generate_work_token()
    cursor.execute('INSERT INTO work_sessions (user_id, work_token) VALUES (?, ?)', (user.id, token))
    conn.commit()
    await ctx.send(f"🔑 **Generated Work Token for {user.name}:** `{token}`")

# ========================== RUN ==========================

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
