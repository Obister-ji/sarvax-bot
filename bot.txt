# bot.py

import discord
from discord.ext import commands
from datetime import datetime
import sqlite3
import random
import string
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Database Setup
conn = sqlite3.connect('work_tracker.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS work_sessions (
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        duration INTEGER,
        work_token TEXT
    )
''')
conn.commit()

# Token Generator
def generate_work_token():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user.name}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Employee Work Hours"))

# Voice Channel Tracker
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

# Commands
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

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
