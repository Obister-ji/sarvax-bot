import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import asyncio
import datetime
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Set your token in environment variable
GUILD_ID = YOUR_GUILD_ID  # Replace with your server ID
LOG_CHANNEL_ID = YOUR_LOG_CHANNEL_ID  # Replace with your log channel ID

class TicketModal(ui.Modal, title="🔧 Create Work Ticket"):
    title = ui.TextInput(label="Task Title", placeholder="Enter task title", max_length=100)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Enter details")
    deadline = ui.TextInput(label="Deadline (YYYY-MM-DD HH:MM)", placeholder="2025-06-20 15:30")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select assignee, priority and tags:", ephemeral=True, view=TicketOptionsView(self.title.value, self.description.value, self.deadline.value, interaction.user))

class TicketOptionsView(ui.View):
    def __init__(self, title, description, deadline, creator):
        super().__init__(timeout=None)
        self.title = title
        self.description = description
        self.deadline = deadline
        self.creator = creator

        self.assignee_select = ui.UserSelect(placeholder="👨‍💼 Select assignee(s)", max_values=3)
        self.priority_select = ui.Select(placeholder="🔴 Select priority", options=[
            discord.SelectOption(label="High", emoji="🔴", value="high"),
            discord.SelectOption(label="Medium", emoji="🟡", value="medium"),
            discord.SelectOption(label="Low", emoji="🟢", value="low")
        ])
        self.tag_input = ui.TextInput(label="Tags", placeholder="#urgent #design", required=False)

        self.add_item(self.assignee_select)
        self.add_item(self.priority_select)
        self.add_item(ui.Button(label="Submit", style=discord.ButtonStyle.success, custom_id="submit_ticket"))

    @ui.button(label="Submit", style=discord.ButtonStyle.green)
    async def submit(self, interaction: discord.Interaction, button: ui.Button):
        embed_color = {
            "high": discord.Color.red(),
            "medium": discord.Color.gold(),
            "low": discord.Color.green()
        }.get(self.priority_select.values[0], discord.Color.blurple())

        embed = discord.Embed(title=f"Ticket: {self.title}", description=self.description, color=embed_color)
        embed.add_field(name="Deadline", value=self.deadline, inline=False)
        embed.add_field(name="Priority", value=self.priority_select.values[0].capitalize())
        embed.add_field(name="Tags", value=self.tag_input.value or "None")
        embed.add_field(name="Assignees", value=", ".join(u.mention for u in self.assignee_select.values))
        embed.set_footer(text=f"Created by {self.creator.display_name}")

        await interaction.response.send_message(embed=embed)

        for user in self.assignee_select.values:
            try:
                await user.send(f"You have been assigned a new task:", embed=embed)
            except:
                pass

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"New ticket created by {self.creator.mention}", embed=embed)

        try:
            dt = datetime.datetime.strptime(self.deadline, "%Y-%m-%d %H:%M")
            seconds_until_deadline = (dt - datetime.datetime.now()).total_seconds()
            if seconds_until_deadline > 0:
                asyncio.create_task(self.send_reminder_later(self.assignee_select.values, embed, seconds_until_deadline))
        except:
            pass

    async def send_reminder_later(self, users, embed, seconds):
        await asyncio.sleep(seconds - 3600)  # 1 hour before
        for u in users:
            try:
                await u.send("Reminder: Your task is due in 1 hour!", embed=embed)
            except:
                pass

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

bot = TicketBot()

@bot.tree.command(name="createticket", description="🔧 Create a new work ticket")
async def create_ticket(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="help", description="❓ Show available bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="❓ Bot Help Menu", color=discord.Color.blue())
    embed.add_field(name="/createticket", value="Create a work ticket", inline=False)
    embed.add_field(name="/stats", value="Show your work stats", inline=False)
    embed.add_field(name="/help", value="Show this help menu", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="📊 View work statistics")
async def stats(interaction: discord.Interaction):
    # Fake stats placeholder
    embed = discord.Embed(title="📊 Your Work Stats", color=discord.Color.purple())
    embed.add_field(name="Completed Tasks", value="12", inline=True)
    embed.add_field(name="Pending Tasks", value="4", inline=True)
    embed.add_field(name="Avg. Completion Time", value="6h 30m", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
