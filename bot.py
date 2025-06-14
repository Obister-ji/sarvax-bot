import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional
import asyncio

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Initialize bot with premium intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Database simulation (replace with real DB in production)
TICKETS_DB = {}
REMINDERS = []
WORK_HOURS = {}  # Format: {user_id: {"date": {"start": time, "end": time, "tasks": []}}}
TICKET_COUNTER = 0

# Premium UI Constants
PRIORITY_OPTIONS = [
    discord.SelectOption(label="🔥 Critical", value="Critical", emoji="🔥", description="Immediate attention required"),
    discord.SelectOption(label="⚠️ High", value="High", emoji="⚠️", description="Important task"),
    discord.SelectOption(label="✨ Medium", value="Medium", emoji="✨", description="Normal priority"),
    discord.SelectOption(label="🌿 Low", value="Low", emoji="🌿", description="Low priority")
]

CATEGORIES = [
    discord.SelectOption(label="💻 IT Support", value="IT"),
    discord.SelectOption(label="👥 HR", value="HR"),
    discord.SelectOption(label="💰 Finance", value="Finance"),
    discord.SelectOption(label="📢 Marketing", value="Marketing"),
    discord.SelectOption(label="📝 General", value="General")
]

STATUS_EMOJIS = {
    "Open": "🔓",
    "In Progress": "🔄",
    "On Hold": "⏸️",
    "Completed": "✅",
    "Rejected": "❌"
}

class Ticket:
    def __init__(self, ticket_id: int, creator: discord.Member, assignee: discord.Member, 
                 title: str, description: str, deadline: str, priority: str, category: str):
        self.id = ticket_id
        self.creator = creator
        self.assignee = assignee
        self.title = title
        self.description = description
        self.deadline = deadline
        self.priority = priority
        self.category = category
        self.status = "Open"
        self.created_at = datetime.now()
        self.comments = []
        self.attachments = []
        self.custom_fields = {}
    
    def to_embed(self) -> discord.Embed:
        """Convert ticket to a beautiful embed"""
        color = {
            "Critical": discord.Color.red(),
            "High": discord.Color.orange(),
            "Medium": discord.Color.gold(),
            "Low": discord.Color.green()
        }.get(self.priority, discord.Color.blue())
        
        embed = discord.Embed(
            title=f"🎫 Ticket #{self.id}: {self.title}",
            description=f"```\n{self.description}\n```",
            color=color,
            timestamp=self.created_at
        )
        
        embed.add_field(name="📋 Category", value=f"{self.category}", inline=True)
        embed.add_field(name="⏱️ Status", value=f"{STATUS_EMOJIS.get(self.status)} {self.status}", inline=True)
        embed.add_field(name="🚨 Priority", value=f"{self.priority}", inline=True)
        embed.add_field(name="📅 Deadline", value=f"`{self.deadline}`", inline=True)
        embed.add_field(name="👤 Created By", value=self.creator.mention, inline=True)
        embed.add_field(name="👷 Assigned To", value=self.assignee.mention, inline=True)
        
        if self.comments:
            last_comment = self.comments[-1]
            embed.add_field(
                name="💬 Last Comment", 
                value=f"**{last_comment['author']}:** {last_comment['content']}", 
                inline=False
            )
        
        if self.attachments:
            embed.add_field(
                name="📎 Attachments", 
                value="\n".join(f"[Attachment {i+1}]({url})" for i, url in enumerate(self.attachments)), 
                inline=False
            )
        
        embed.set_footer(text=f"Created at • Ticket ID: {self.id}")
        embed.set_thumbnail(url="https://i.imgur.com/7W6mEfK.png")
        
        return embed

class TicketModal(ui.Modal, title="✨ Create Premium Ticket"):
    task_title = ui.TextInput(
        label="Task Title", 
        placeholder="e.g., Fix dashboard UI bugs",
        style=discord.TextStyle.short,
        max_length=100
    )
    
    task_description = ui.TextInput(
        label="Task Description", 
        placeholder="Describe the task in detail...", 
        style=discord.TextStyle.long
    )
    
    deadline = ui.TextInput(
        label="Deadline (DD/MM/YYYY)", 
        placeholder="e.g., 30/06/2023",
        style=discord.TextStyle.short,
        max_length=10
    )

    category = ui.TextInput(
        label="Category (IT/HR/Finance/Marketing/General)",
        placeholder="e.g., IT",
        style=discord.TextStyle.short,
        max_length=20
    )

    priority = ui.TextInput(
        label="Priority (Critical/High/Medium/Low)",
        placeholder="e.g., High",
        style=discord.TextStyle.short,
        max_length=10
    )

    def __init__(self, assignees: List[discord.Member]):
        super().__init__(timeout=300)
        self.assignees = assignees
        self.assignee_select = None
        
        # Create a view for the select menu that will be sent after modal submission
        self.assignee_view = ui.View(timeout=180)
        self.assignee_select = ui.Select(
            placeholder="👤 Select Assignee",
            options=[discord.SelectOption(label=member.display_name, value=str(member.id)) for member in assignees],
            min_values=1,
            max_values=1
        )
        self.assignee_view.add_item(self.assignee_select)
    
    async def on_submit(self, interaction: discord.Interaction):
        global TICKET_COUNTER
        
        # First send the assignee selection
        await interaction.response.send_message(
            "Please select an assignee for this ticket:",
            view=self.assignee_view,
            ephemeral=True
        )
        
        # Wait for the user to select an assignee
        try:
            assignee_interaction = await bot.wait_for(
                "interaction",
                check=lambda i: i.data.get("custom_id") == self.assignee_select.custom_id and i.user.id == interaction.user.id,
                timeout=180
            )
        except asyncio.TimeoutError:
            await interaction.followup.send("Ticket creation timed out.", ephemeral=True)
            return
        
        assignee_id = int(self.assignee_select.values[0])
        assignee = interaction.guild.get_member(assignee_id)
        
        TICKET_COUNTER += 1
        ticket_id = TICKET_COUNTER
        
        ticket = Ticket(
            ticket_id=ticket_id,
            creator=interaction.user,
            assignee=assignee,
            title=str(self.task_title),
            description=str(self.task_description),
            deadline=str(self.deadline),
            priority=str(self.priority),
            category=str(self.category)
        )
        
        TICKETS_DB[ticket_id] = ticket
        
        embed = ticket.to_embed()
        embed.set_author(name="New Ticket Created!", icon_url=interaction.user.avatar.url)
        
        view = TicketActionsView(ticket_id)
        
        await assignee_interaction.response.send_message(
            content=f"🎉 Ticket #{ticket_id} created successfully!",
            embed=embed,
            view=view
        )
        
        try:
            dm_embed = discord.Embed(
                title=f"📬 New Ticket Assigned: #{ticket_id}",
                description=f"You've been assigned a new ticket by {interaction.user.mention}",
                color=discord.Color.blurple()
            )
            dm_embed.add_field(name="Title", value=ticket.title, inline=False)
            dm_embed.add_field(name="Priority", value=ticket.priority, inline=True)
            dm_embed.add_field(name="Deadline", value=f"`{ticket.deadline}`", inline=True)
            dm_embed.set_thumbnail(url="https://i.imgur.com/J5h8x2V.png")
            dm_embed.set_footer(text="Please respond promptly to this ticket")
            
            await assignee.send(embed=dm_embed)
        except discord.Forbidden:
            pass

class TicketActionsView(ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @ui.button(label="📝 Add Comment", style=discord.ButtonStyle.blurple, custom_id="add_comment")
    async def add_comment(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(CommentModal(self.ticket_id))
    
    @ui.button(label="📎 Attach File", style=discord.ButtonStyle.green, custom_id="attach_file")
    async def attach_file(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "📤 Please upload your file in this channel. It will be automatically attached to the ticket.",
            ephemeral=True
        )
    
    @ui.button(label="⏰ Set Reminder", style=discord.ButtonStyle.grey, custom_id="set_reminder")
    async def set_reminder(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReminderModal(self.ticket_id))
    
    @ui.button(label="🔄 Transfer", style=discord.ButtonStyle.red, custom_id="transfer_ticket")
    async def transfer_ticket(self, interaction: discord.Interaction, button: ui.Button):
        ticket = TICKETS_DB.get(self.ticket_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        
        if interaction.user.id not in [ticket.assignee.id, ticket.creator.id]:
            await interaction.response.send_message("🚫 You don't have permission to transfer this ticket.", ephemeral=True)
            return
        
        view = TransferView(self.ticket_id, interaction.user)
        await interaction.response.send_message(
            f"🔄 Select a new assignee for ticket #{self.ticket_id}:",
            view=view,
            ephemeral=True
        )

# [Rest of your classes (CommentModal, ReminderModal, TransferView, WorkHoursModal) remain the same]

@bot.tree.command(name="new", description="✨ Create a new premium support ticket")
async def create_ticket(interaction: discord.Interaction):
    members = [m for m in interaction.guild.members if not m.bot]
    if not members:
        embed = discord.Embed(
            description="❌ No team members available for assignment",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.send_modal(TicketModal(members))

# [Rest of your commands (ticket, mytickets, loghours, workreport, help) remain the same]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✨ Premium bot ready as {bot.user}")
    
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="premium tickets and work hours"
    )
    await bot.change_presence(activity=activity)
    check_reminders.start()

# [Rest of your event handlers remain the same]

bot.run(DISCORD_BOT_TOKEN)