import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from datetime import datetime, timedelta
import os
import random
import asyncio
from typing import List, Dict, Optional, Union
import math
import pytz

# Load environment variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", 0))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))

# Initialize bot with premium intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Database simulation (replace with real DB in production)
TICKETS_DB = {}
REMINDERS = []
WORK_HOURS = {}  
TICKET_COUNTER = 0
USER_STATS = {}  # Format: {user_id: {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0}}
ACTIVE_USERS = {}  # Track active users for coin rewards
GAMBLING_GAMES = {}  # Track active gambling games
JACKPOT_POOL = {"total": 0, "participants": {}}
EVENT = None  # Current active event
QUOTES = [
    "Every idea counts, every second builds value. Welcome to SARVAX.",
    "Greatness starts with a single step. Welcome aboard!",
    "Your potential is limitless. Let's build something amazing!",
    "Innovation begins here. Welcome to the team!",
    "Success is a team sport. Glad you're on our side!"
]
WELCOME_GIFS = [
    "https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif",
    "https://media.giphy.com/media/l0HU7ZeB2lJQY2vKU/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
    "https://media.giphy.com/media/3o7TKsQ8UQ1h6RakUw/giphy.gif"
]

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

# Shop items
SHOP_ITEMS = {
    "Custom Role": {"price": 5000, "description": "Get your own custom role with unique color"},
    "VIP Perks": {"price": 3000, "description": "Exclusive VIP channel access and perks"},
    "Priority Support": {"price": 2000, "description": "Jump to the front of support queues"},
    "Custom Emoji": {"price": 8000, "description": "Add your own custom emoji to the server"},
    "Double Coins (1 day)": {"price": 1500, "description": "Earn double coins for 24 hours"}
}

# Badges
BADGES = {
    "Early Adopter": "🥇",
    "Coin Millionaire": "💰",
    "Task Master": "✅",
    "Legendary Worker": "🏆",
    "Gambling King": "🎰"
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
        self.completed_at = None
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
        
        if self.status == "Completed" and self.completed_at:
            embed.add_field(
                name="⏱️ Completion Time",
                value=f"Completed in {(self.completed_at - self.created_at).total_seconds() / 3600:.1f} hours",
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
    
    @ui.button(label="✅ Mark Complete", style=discord.ButtonStyle.green, custom_id="complete_ticket")
    async def complete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        ticket = TICKETS_DB.get(self.ticket_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        
        if interaction.user.id not in [ticket.assignee.id, ticket.creator.id]:
            await interaction.response.send_message("🚫 You don't have permission to complete this ticket.", ephemeral=True)
            return
        
        ticket.status = "Completed"
        ticket.completed_at = datetime.now()
        
        # Calculate coins based on completion time
        deadline = datetime.strptime(ticket.deadline, "%d/%m/%Y")
        if ticket.completed_at > deadline:
            hours_late = (ticket.completed_at - deadline).total_seconds() / 3600
            coins_lost = min(0.1 * hours_late, 10)  # Max 10 coins penalty
            user_id = str(interaction.user.id)
            if user_id in USER_STATS:
                USER_STATS[user_id]["coins"] = max(0, USER_STATS[user_id]["coins"] - coins_lost)
        
        embed = ticket.to_embed()
        embed.set_author(name=f"Ticket #{self.ticket_id} Completed!", icon_url=interaction.user.avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        try:
            # Notify creator
            creator_embed = discord.Embed(
                title=f"✅ Ticket Completed: #{self.ticket_id}",
                description=f"Your ticket has been completed by {interaction.user.mention}",
                color=discord.Color.green()
            )
            await ticket.creator.send(embed=creator_embed)
        except discord.Forbidden:
            pass

class CommentModal(ui.Modal, title="💬 Add Comment"):
    comment = ui.TextInput(
        label="Your Comment", 
        style=discord.TextStyle.long,
        placeholder="Type your comment here...",
        required=True
    )

    def __init__(self, ticket_id: int):
        super().__init__()
        self.ticket_id = ticket_id

    async def on_submit(self, interaction: discord.Interaction):
        ticket = TICKETS_DB.get(self.ticket_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        
        ticket.comments.append({
            "author": interaction.user.display_name,
            "content": str(self.comment),
            "timestamp": datetime.now()
        })
        
        embed = discord.Embed(
            description=f"💬 Comment added to ticket #{self.ticket_id}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        channel = interaction.channel
        try:
            message = await channel.fetch_message(interaction.message.id)
            await message.edit(embed=ticket.to_embed())
        except:
            pass

class ReminderModal(ui.Modal, title="⏰ Set Reminder"):
    when = ui.TextInput(
        label="Reminder Time (DD/MM/YYYY HH:MM)", 
        placeholder="e.g., 30/06/2023 14:30",
        required=True
    )
    note = ui.TextInput(
        label="Reminder Note (Optional)", 
        style=discord.TextStyle.long,
        required=False
    )

    def __init__(self, ticket_id: int):
        super().__init__()
        self.ticket_id = ticket_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            reminder_time = datetime.strptime(str(self.when), "%d/%m/%Y %H:%M")
            if reminder_time < datetime.now():
                raise ValueError("Reminder time must be in the future")
            
            REMINDERS.append({
                "ticket_id": self.ticket_id,
                "user_id": interaction.user.id,
                "time": reminder_time,
                "note": str(self.note) if self.note else None
            })
            
            embed = discord.Embed(
                description=f"⏰ Reminder set for {reminder_time.strftime('%d %b %Y at %H:%M')}",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError as e:
            embed = discord.Embed(
                description=f"❌ Invalid time format: {e}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class TransferView(ui.View):
    def __init__(self, ticket_id: int, current_assignee: discord.Member):
        super().__init__(timeout=120)
        self.ticket_id = ticket_id
        self.current_assignee = current_assignee
        
        members = [
            m for m in current_assignee.guild.members 
            if not m.bot and m.id != current_assignee.id
        ]
        
        options = [
            discord.SelectOption(
                label=f"{m.display_name} ({m.name})",
                value=str(m.id),
                emoji="👤"
            ) for m in members
        ]
        
        self.select = ui.Select(
            placeholder="👥 Select new assignee...",
            options=options,
            min_values=1,
            max_values=1
        )
        
        self.add_item(self.select)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.current_assignee.id
    
    @ui.button(label="✅ Confirm Transfer", style=discord.ButtonStyle.green, row=1)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        new_assignee_id = int(self.select.values[0])
        ticket = TICKETS_DB.get(self.ticket_id)
        
        if not ticket:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
            return
        
        new_assignee = interaction.guild.get_member(new_assignee_id)
        old_assignee = ticket.assignee
        ticket.assignee = new_assignee
        
        embed = discord.Embed(
            description=f"🔄 Ticket #{self.ticket_id} transferred to {new_assignee.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        try:
            new_assignee_embed = discord.Embed(
                title=f"📬 Ticket Assigned: #{self.ticket_id}",
                description=f"You've been assigned a ticket by {old_assignee.mention}",
                color=discord.Color.blurple()
            )
            new_assignee_embed.add_field(name="Title", value=ticket.title, inline=False)
            new_assignee_embed.set_footer(text=f"Priority: {ticket.priority} | Deadline: {ticket.deadline}")
            await new_assignee.send(embed=new_assignee_embed)
            
            old_assignee_embed = discord.Embed(
                title=f"🔄 Ticket Transferred: #{self.ticket_id}",
                description=f"You've transferred a ticket to {new_assignee.mention}",
                color=discord.Color.blue()
            )
            await old_assignee.send(embed=old_assignee_embed)
        except discord.Forbidden:
            pass
        
        self.stop()

    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.red, row=1)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            description="🚫 Ticket transfer cancelled",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()

class WorkHoursModal(ui.Modal, title="⏱️ Log Work Hours"):
    date = ui.TextInput(
        label="Date (DD/MM/YYYY)", 
        placeholder="e.g., 14/06/2025",
        style=discord.TextStyle.short,
        required=True
    )
    start_time = ui.TextInput(
        label="Start Time (HH:MM)", 
        placeholder="e.g., 09:00",
        style=discord.TextStyle.short,
        required=True
    )
    end_time = ui.TextInput(
        label="End Time (HH:MM)", 
        placeholder="e.g., 17:30",
        style=discord.TextStyle.short,
        required=True
    )
    tasks = ui.TextInput(
        label="Tasks Completed", 
        placeholder="Describe what you worked on...",
        style=discord.TextStyle.long,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate date and times
            work_date = datetime.strptime(str(self.date), "%d/%m/%Y").date()
            start = datetime.strptime(str(self.start_time), "%H:%M").time()
            end = datetime.strptime(str(self.end_time), "%H:%M").time()
            
            if end <= start:
                raise ValueError("End time must be after start time")
            
            # Calculate hours worked
            start_dt = datetime.combine(work_date, start)
            end_dt = datetime.combine(work_date, end)
            hours_worked = round((end_dt - start_dt).total_seconds() / 3600, 2)
            
            # Store work hours
            user_id = str(interaction.user.id)
            if user_id not in WORK_HOURS:
                WORK_HOURS[user_id] = {}
                
            date_str = work_date.strftime("%Y-%m-%d")
            WORK_HOURS[user_id][date_str] = {
                "start": str(self.start_time),
                "end": str(self.end_time),
                "hours": hours_worked,
                "tasks": str(self.tasks) if self.tasks else "No details provided"
            }
            
            # Award coins for work hours
            if user_id not in USER_STATS:
                USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
            
            coins_earned = hours_worked * (2 if EVENT and EVENT["type"] == "Double Coins" else 1)
            USER_STATS[user_id]["coins"] += coins_earned
            USER_STATS[user_id]["xp"] += hours_worked * 10
            
            # Check for level up
            xp_needed = USER_STATS[user_id]["level"] * 100
            if USER_STATS[user_id]["xp"] >= xp_needed:
                USER_STATS[user_id]["level"] += 1
                USER_STATS[user_id]["xp"] = 0
                level_up_msg = f"🎉 Level up! You're now level {USER_STATS[user_id]['level']}!"
            else:
                level_up_msg = ""
            
            embed = discord.Embed(
                title="⏱️ Work Hours Logged",
                description=f"Successfully recorded your work hours for {work_date.strftime('%d %b %Y')}",
                color=discord.Color.green()
            )
            embed.add_field(name="Start Time", value=str(self.start_time), inline=True)
            embed.add_field(name="End Time", value=str(self.end_time), inline=True)
            embed.add_field(name="Total Hours", value=f"{hours_worked} hours", inline=True)
            embed.add_field(name="Coins Earned", value=f"🪙 {coins_earned} Obiz Coins", inline=False)
            if level_up_msg:
                embed.add_field(name="Level Up!", value=level_up_msg, inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Error Logging Hours",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ShopView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        
    @ui.select(
        placeholder="🛍️ Select an item to purchase...",
        options=[
            discord.SelectOption(
                label=f"{item} - 🪙 {details['price']}",
                description=details["description"],
                value=item
            ) for item, details in SHOP_ITEMS.items()
        ],
        min_values=1,
        max_values=1
    )
    async def shop_select(self, interaction: discord.Interaction, select: ui.Select):
        item = select.values[0]
        user_id = str(interaction.user.id)
        
        if user_id not in USER_STATS:
            USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
        
        if USER_STATS[user_id]["coins"] < SHOP_ITEMS[item]["price"]:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need 🪙 {SHOP_ITEMS[item]['price'] - USER_STATS[user_id]['coins']} more coins to buy {item}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Process purchase
        USER_STATS[user_id]["coins"] -= SHOP_ITEMS[item]["price"]
        
        if item == "Custom Role":
            # Prompt for role details
            await interaction.response.send_modal(CustomRoleModal())
        else:
            embed = discord.Embed(
                title="🎉 Purchase Successful!",
                description=f"You've purchased: **{item}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Description", value=SHOP_ITEMS[item]["description"], inline=False)
            embed.add_field(name="Remaining Balance", value=f"🪙 {USER_STATS[user_id]['coins']}", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

class CustomRoleModal(ui.Modal, title="🎨 Create Custom Role"):
    role_name = ui.TextInput(
        label="Role Name",
        placeholder="Enter your desired role name",
        style=discord.TextStyle.short,
        max_length=100
    )
    
    role_color = ui.TextInput(
        label="Role Color (hex code)",
        placeholder="e.g., #FF0000 for red",
        style=discord.TextStyle.short,
        max_length=7
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate color
            color = discord.Color.from_str(str(self.role_color))
            
            # Create the role
            role = await interaction.guild.create_role(
                name=str(self.role_name),
                color=color,
                reason=f"Custom role purchased by {interaction.user}"
            )
            
            # Assign the role to the user
            await interaction.user.add_roles(role)
            
            embed = discord.Embed(
                title="🎉 Custom Role Created!",
                description=f"Your new role **{role.name}** has been created and assigned to you!",
                color=color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Color",
                description="Please provide a valid hex color code (e.g., #FF0000)",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class CoinFlipView(ui.View):
    def __init__(self, amount: int, choice: str, interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.amount = amount
        self.choice = choice
        self.interaction = interaction
        self.user_id = str(interaction.user.id)
        
    @ui.button(label="Flip the Coin!", style=discord.ButtonStyle.blurple, emoji="🪙")
    async def flip_coin(self, interaction: discord.Interaction, button: ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This coin flip isn't yours!", ephemeral=True)
            return
        
        # Deduct coins first
        if self.user_id not in USER_STATS:
            USER_STATS[self.user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
        
        if USER_STATS[self.user_id]["coins"] < self.amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description="You don't have enough coins for this bet!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        USER_STATS[self.user_id]["coins"] -= self.amount
        
        # Animate the flip
        flip_gif = "https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif"
        embed = discord.Embed(title="🪙 Coin Flip in Progress...", color=discord.Color.gold())
        embed.set_image(url=flip_gif)
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Wait for dramatic effect
        await asyncio.sleep(3)
        
        # Determine result
        result = random.choice(["Heads", "Tails"])
        win = result.lower() == self.choice.lower()
        
        # Update coins
        if win:
            USER_STATS[self.user_id]["coins"] += self.amount * 2
            result_msg = f"🎉 You won 🪙 {self.amount * 2}!"
            color = discord.Color.green()
            gif = "https://media.giphy.com/media/xUOxfjsW9fWPqEWouI/giphy.gif"
        else:
            result_msg = f"😢 You lost 🪙 {self.amount}."
            color = discord.Color.red()
            gif = "https://media.giphy.com/media/l3V0j3ytFyGHqiV7W/giphy.gif"
        
        # Send result
        embed = discord.Embed(
            title=f"🪙 Coin Flip: {result}",
            description=f"You chose **{self.choice}**\n{result_msg}",
            color=color
        )
        embed.set_image(url=gif)
        embed.set_footer(text=f"Current balance: 🪙 {USER_STATS[self.user_id]['coins']}")
        await interaction.edit_original_response(embed=embed)

class JackpotView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @ui.button(label="🎰 Join Jackpot!", style=discord.ButtonStyle.green, custom_id="jackpot_join")
    async def join_jackpot(self, interaction: discord.Interaction, button: ui.Button):
        user_id = str(interaction.user.id)
        
        if user_id not in USER_STATS:
            USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
        
        if USER_STATS[user_id]["coins"] < 100:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description="You need at least 🪙 100 to join the jackpot!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if user_id in JACKPOT_POOL["participants"]:
            embed = discord.Embed(
                title="⚠️ Already Joined",
                description="You're already in the jackpot pool!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Deduct coins and add to pool
        USER_STATS[user_id]["coins"] -= 100
        JACKPOT_POOL["total"] += 100
        JACKPOT_POOL["participants"][user_id] = interaction.user.display_name
        
        embed = discord.Embed(
            title="🎰 Jackpot Joined!",
            description=f"You've entered the jackpot with 🪙 100!\nCurrent pool: 🪙 {JACKPOT_POOL['total']}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="newticket", description="🎟️ Create a new premium support ticket")
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

async def ticket_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[int]]:
    tickets = []
    for ticket in TICKETS_DB.values():
        if interaction.user.id in [ticket.assignee.id, ticket.creator.id]:
            if current.lower() in str(ticket.id) or current.lower() in ticket.title.lower():
                emoji = STATUS_EMOJIS.get(ticket.status, "📌")
                tickets.append(
                    app_commands.Choice(
                        name=f"#{ticket.id} {emoji} {ticket.title[:50]}",
                        value=ticket.id
                    )
                )
    return tickets[:25]

@bot.tree.command(name="ticket", description="🔍 View a specific ticket")
@app_commands.autocomplete(ticket_id=ticket_autocomplete)
async def view_ticket(interaction: discord.Interaction, ticket_id: int):
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        embed = discord.Embed(
            description=f"❌ Ticket #{ticket_id} not found",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if interaction.user.id not in [ticket.assignee.id, ticket.creator.id]:
        embed = discord.Embed(
            description="🚫 You don't have permission to view this ticket",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = ticket.to_embed()
    view = TicketActionsView(ticket_id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="mytickets", description="📋 View all your assigned tickets")
async def my_tickets(interaction: discord.Interaction):
    user_tickets = [
        t for t in TICKETS_DB.values() 
        if t.assignee.id == interaction.user.id or t.creator.id == interaction.user.id
    ]
    
    if not user_tickets:
        embed = discord.Embed(
            description="📭 You have no assigned tickets",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embeds = []
    for i, ticket in enumerate(user_tickets[:10], 1):
        embed = discord.Embed(
            title=f"📋 Your Tickets ({i}/{len(user_tickets[:10])})",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name=f"#{ticket.id} {STATUS_EMOJIS.get(ticket.status)} {ticket.title}",
            value=f"**Priority:** {ticket.priority}\n**Deadline:** {ticket.deadline}",
            inline=False
        )
        embeds.append(embed)
    
    await interaction.response.send_message(embeds=embeds, ephemeral=True)

@bot.tree.command(name="loghours", description="⏱️ Log your work hours")
async def log_hours(interaction: discord.Interaction):
    await interaction.response.send_modal(WorkHoursModal())

@bot.tree.command(name="workreport", description="📊 Show your work hours report")
async def work_report(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in WORK_HOURS or not WORK_HOURS[user_id]:
        embed = discord.Embed(
            description="📭 You have no logged work hours",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    total_hours = 0
    embed = discord.Embed(
        title=f"⏱️ Work Report for {interaction.user.display_name}",
        color=discord.Color.gold()
    )
    
    for date, entry in WORK_HOURS[user_id].items():
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        embed.add_field(
            name=f"📅 {date_obj.strftime('%d %b %Y')}",
            value=f"⏰ {entry['start']} - {entry['end']} ({entry['hours']} hrs)\n📝 {entry['tasks']}",
            inline=False
        )
        total_hours += entry['hours']
    
    embed.set_footer(text=f"Total Hours: {total_hours}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="balance", description="💰 Check your Obiz Coin balance")
async def check_balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    embed = discord.Embed(
        title=f"💰 {interaction.user.display_name}'s Balance",
        color=discord.Color.gold()
    )
    embed.add_field(name="🪙 Obiz Coins", value=f"{USER_STATS[user_id]['coins']}", inline=True)
    embed.add_field(name="📊 Level", value=f"{USER_STATS[user_id]['level']}", inline=True)
    embed.add_field(name="✨ XP", value=f"{USER_STATS[user_id]['xp']}/{USER_STATS[user_id]['level'] * 100}", inline=True)
    
    if USER_STATS[user_id]["badges"]:
        badges = " ".join([BADGES.get(b, "") for b in USER_STATS[user_id]["badges"]])
        embed.add_field(name="🏆 Badges", value=badges, inline=False)
    
    embed.set_thumbnail(url=interaction.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="🎁 Claim your daily Obiz Coin reward")
async def daily_reward(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    now = datetime.now()
    last_daily = USER_STATS[user_id]["last_daily"]
    
    if last_daily and (now - last_daily).days < 1:
        next_claim = (last_daily + timedelta(days=1)).strftime("%H:%M %p")
        embed = discord.Embed(
            title="⏳ Already Claimed",
            description=f"You've already claimed your daily reward today!\nNext claim available at {next_claim}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Calculate streak
    if last_daily and (now - last_daily).days == 1:
        USER_STATS[user_id]["streak"] += 1
    else:
        USER_STATS[user_id]["streak"] = 1
    
    # Calculate reward (50-150 coins + streak bonus)
    base_reward = random.randint(50, 150)
    streak_bonus = min(USER_STATS[user_id]["streak"] * 10, 100)  # Max 100 bonus
    total_reward = base_reward + streak_bonus
    
    # Apply event multiplier if active
    if EVENT and EVENT["type"] == "Double Coins":
        total_reward *= 2
    
    USER_STATS[user_id]["coins"] += total_reward
    USER_STATS[user_id]["last_daily"] = now
    
    embed = discord.Embed(
        title="🎁 Daily Reward Claimed!",
        description=f"Here's your daily Obiz Coin reward!",
        color=discord.Color.green()
    )
    embed.add_field(name="Base Reward", value=f"🪙 {base_reward}", inline=True)
    embed.add_field(name="Streak Bonus", value=f"🔥 +{streak_bonus}", inline=True)
    if EVENT and EVENT["type"] == "Double Coins":
        embed.add_field(name="Event Bonus", value=f"🎉 2x Multiplier!", inline=True)
    embed.add_field(name="Total Received", value=f"🪙 {total_reward}", inline=False)
    embed.add_field(name="Current Streak", value=f"🔥 {USER_STATS[user_id]['streak']} days", inline=False)
    embed.add_field(name="New Balance", value=f"💰 {USER_STATS[user_id]['coins']}", inline=False)
    embed.set_footer(text="Come back tomorrow for more!")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="🛍️ Spend your Obiz Coins in the shop")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛍️ Obiz Coin Shop",
        description="Spend your hard-earned Obiz Coins on awesome perks!",
        color=discord.Color.purple()
    )
    
    for item, details in SHOP_ITEMS.items():
        embed.add_field(
            name=f"{item} - 🪙 {details['price']}",
            value=details["description"],
            inline=False
        )
    
    user_id = str(interaction.user.id)
    if user_id in USER_STATS:
        embed.set_footer(text=f"Your balance: 🪙 {USER_STATS[user_id]['coins']}")
    else:
        embed.set_footer(text="New users start with 🪙 1000")
    
    await interaction.response.send_message(embed=embed, view=ShopView())

@bot.tree.command(name="transfer", description="💸 Transfer Obiz Coins to another user")
async def transfer_coins(interaction: discord.Interaction, recipient: discord.Member, amount: int):
    sender_id = str(interaction.user.id)
    recipient_id = str(recipient.id)
    
    if sender_id == recipient_id:
        embed = discord.Embed(
            title="❌ Invalid Transfer",
            description="You can't send coins to yourself!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="You must transfer at least 🪙 1",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Initialize sender and recipient if needed
    if sender_id not in USER_STATS:
        USER_STATS[sender_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    if recipient_id not in USER_STATS:
        USER_STATS[recipient_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    if USER_STATS[sender_id]["coins"] < amount:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have 🪙 {USER_STATS[sender_id]['coins']}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Perform transfer
    USER_STATS[sender_id]["coins"] -= amount
    USER_STATS[recipient_id]["coins"] += amount
    
    embed = discord.Embed(
        title="💸 Transfer Complete!",
        description=f"You've sent 🪙 {amount} to {recipient.mention}",
        color=discord.Color.green()
    )
    embed.add_field(name="Your New Balance", value=f"🪙 {USER_STATS[sender_id]['coins']}", inline=False)
    await interaction.response.send_message(embed=embed)
    
    try:
        recipient_embed = discord.Embed(
            title="🎉 You Received Obiz Coins!",
            description=f"{interaction.user.mention} sent you 🪙 {amount}",
            color=discord.Color.green()
        )
        recipient_embed.add_field(name="Your New Balance", value=f"🪙 {USER_STATS[recipient_id]['coins']}", inline=False)
        await recipient.send(embed=recipient_embed)
    except discord.Forbidden:
        pass

@bot.tree.command(name="coinflip", description="🪙 Flip a coin to win Obiz Coins")
async def coin_flip(interaction: discord.Interaction, amount: int, choice: str):
    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="You must bet at least 🪙 1",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if choice.lower() not in ["heads", "tails"]:
        embed = discord.Embed(
            title="❌ Invalid Choice",
            description="Please choose either 'heads' or 'tails'",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    if USER_STATS[user_id]["coins"] < amount:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have 🪙 {USER_STATS[user_id]['coins']}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"You're betting 🪙 {amount} on **{choice.capitalize()}**\nClick the button below to flip!",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Current balance: 🪙 {USER_STATS[user_id]['coins']}")
    
    view = CoinFlipView(amount, choice, interaction)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="dice", description="🎲 Roll a dice to win Obiz Coins")
async def dice_roll(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="You must bet at least 🪙 1",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    if USER_STATS[user_id]["coins"] < amount:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have 🪙 {USER_STATS[user_id]['coins']}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Deduct coins first
    USER_STATS[user_id]["coins"] -= amount
    
    # Animate the roll
    roll_gif = "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif"
    embed = discord.Embed(title="🎲 Rolling Dice...", color=discord.Color.gold())
    embed.set_image(url=roll_gif)
    await interaction.response.send_message(embed=embed)
    
    # Wait for dramatic effect
    await asyncio.sleep(3)
    
    # Determine result
    result = random.randint(1, 6)
    win = result in [5, 6]
    
    # Update coins
    if win:
        winnings = amount * 2
        USER_STATS[user_id]["coins"] += winnings
        result_msg = f"🎉 You rolled a {result} and won 🪙 {winnings}!"
        color = discord.Color.green()
        gif = "https://media.giphy.com/media/xUOxfjsW9fWPqEWouI/giphy.gif"
    else:
        result_msg = f"😢 You rolled a {result} and lost 🪙 {amount}."
        color = discord.Color.red()
        gif = "https://media.giphy.com/media/l3V0j3ytFyGHqiV7W/giphy.gif"
    
    # Send result
    embed = discord.Embed(
        title=f"🎲 Dice Roll: {result}",
        description=result_msg,
        color=color
    )
    embed.set_image(url=gif)
    embed.set_footer(text=f"Current balance: 🪙 {USER_STATS[user_id]['coins']}")
    await interaction.edit_original_response(embed=embed)

@bot.tree.command(name="jackpot", description="🎰 Join the Obiz Coin jackpot (🪙 100 entry)")
async def jackpot(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎰 Obiz Coin Jackpot",
        description="Join the jackpot for a chance to win big!\nEntry fee: 🪙 100\nWinner takes all!",
        color=discord.Color.purple()
    )
    embed.add_field(name="Current Pool", value=f"🪙 {JACKPOT_POOL['total']}", inline=True)
    embed.add_field(name="Participants", value=f"👥 {len(JACKPOT_POOL['participants'])}", inline=True)
    embed.set_footer(text="Drawing occurs when pool reaches 🪙 5000 or every 24 hours")
    
    view = JackpotView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="profile", description="📊 View your profile and stats")
async def profile(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    # Calculate stats
    tickets_created = len([t for t in TICKETS_DB.values() if t.creator.id == interaction.user.id])
    tickets_completed = len([t for t in TICKETS_DB.values() if t.assignee.id == interaction.user.id and t.status == "Completed"])
    total_hours = sum(day["hours"] for day in WORK_HOURS.get(user_id, {}).values())
    
    embed = discord.Embed(
        title=f"📊 {interaction.user.display_name}'s Profile",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=interaction.user.avatar.url)
    
    # Basic info
    embed.add_field(name="🪙 Obiz Coins", value=f"{USER_STATS[user_id]['coins']}", inline=True)
    embed.add_field(name="📊 Level", value=f"{USER_STATS[user_id]['level']}", inline=True)
    embed.add_field(name="✨ XP", value=f"{USER_STATS[user_id]['xp']}/{USER_STATS[user_id]['level'] * 100}", inline=True)
    
    # Stats
    embed.add_field(name="🎟️ Tickets Created", value=tickets_created, inline=True)
    embed.add_field(name="✅ Tickets Completed", value=tickets_completed, inline=True)
    embed.add_field(name="⏱️ Hours Worked", value=f"{total_hours:.1f}", inline=True)
    
    # Badges
    if USER_STATS[user_id]["badges"]:
        badges = " ".join([BADGES.get(b, "") for b in USER_STATS[user_id]["badges"]])
        embed.add_field(name="🏆 Badges", value=badges, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="🏆 View leaderboards")
async def leaderboard(interaction: discord.Interaction, metric: str = "coins"):
    if metric.lower() not in ["coins", "level", "tickets", "hours"]:
        embed = discord.Embed(
            title="❌ Invalid Metric",
            description="Available metrics: coins, level, tickets, hours",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Prepare leaderboard data
    leaderboard_data = []
    for user_id, stats in USER_STATS.items():
        user = interaction.guild.get_member(int(user_id))
        if not user:
            continue
        
        if metric == "coins":
            value = stats["coins"]
        elif metric == "level":
            value = stats["level"]
        elif metric == "tickets":
            value = len([t for t in TICKETS_DB.values() if t.assignee.id == user.id and t.status == "Completed"])
        elif metric == "hours":
            value = sum(day["hours"] for day in WORK_HOURS.get(user_id, {}).values())
        
        leaderboard_data.append((user.display_name, value))
    
    # Sort and limit to top 10
    leaderboard_data.sort(key=lambda x: x[1], reverse=True)
    leaderboard_data = leaderboard_data[:10]
    
    if not leaderboard_data:
        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="No data available yet!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"🏆 {metric.capitalize()} Leaderboard",
        color=discord.Color.gold()
    )
    
    for i, (name, value) in enumerate(leaderboard_data, 1):
        embed.add_field(
            name=f"{i}. {name}",
            value=f"{value} {'🪙' if metric == 'coins' else '📊' if metric == 'level' else '✅' if metric == 'tickets' else '⏱️'}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="freelance", description="💼 Browse available freelance tasks")
async def freelance(interaction: discord.Interaction):
    # Get open tickets not assigned to anyone
    freelance_tasks = [t for t in TICKETS_DB.values() if t.status == "Open" and t.assignee is None]
    
    if not freelance_tasks:
        embed = discord.Embed(
            title="💼 Freelance Tasks",
            description="No available tasks at the moment. Check back later!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        return
    
    embed = discord.Embed(
        title="💼 Available Freelance Tasks",
        description="Claim one of these tasks to earn Obiz Coins!",
        color=discord.Color.green()
    )
    
    for task in freelance_tasks[:5]:
        embed.add_field(
            name=f"🎟️ #{task.id} - {task.title}",
            value=f"**Reward:** 🪙 {100 * (1 + ['Low', 'Medium', 'High', 'Critical'].index(task.priority))}\n**Deadline:** {task.deadline}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="refer", description="📨 Refer a friend and earn Obiz Coins")
async def refer_friend(interaction: discord.Interaction, friend: discord.Member):
    if friend.bot:
        embed = discord.Embed(
            title="❌ Invalid Referral",
            description="You can't refer bots!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if friend.id == interaction.user.id:
        embed = discord.Embed(
            title="❌ Invalid Referral",
            description="You can't refer yourself!",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    if user_id not in USER_STATS:
        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    # Check if friend is new (has no coins yet)
    friend_id = str(friend.id)
    if friend_id in USER_STATS and USER_STATS[friend_id]["coins"] < 1000:
        embed = discord.Embed(
            title="❌ Already Referred",
            description="This user has already been referred by someone else",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Award coins
    USER_STATS[user_id]["coins"] += 300
    
    embed = discord.Embed(
        title="🎉 Referral Successful!",
        description=f"You've referred {friend.mention} and earned 🪙 300!",
        color=discord.Color.green()
    )
    embed.add_field(name="Your New Balance", value=f"🪙 {USER_STATS[user_id]['coins']}", inline=False)
    await interaction.response.send_message(embed=embed)
    
    try:
        # Initialize friend's account
        if friend_id not in USER_STATS:
            USER_STATS[friend_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
        
        friend_embed = discord.Embed(
            title="🎉 You've Been Referred!",
            description=f"{interaction.user.mention} referred you to the server!",
            color=discord.Color.green()
        )
        friend_embed.add_field(name="Welcome Bonus", value="You've received 🪙 1000 to get started!", inline=False)
        await friend.send(embed=friend_embed)
    except discord.Forbidden:
        pass

@bot.tree.command(name="help", description="ℹ️ Show premium bot help")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ Premium Ticket Bot Help",
        description="Manage support tickets, work hours, and Obiz Coin economy!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🎫 Ticket Commands",
        value="""`/newticket` - Create a new ticket
`/ticket` - View a specific ticket
`/mytickets` - List your tickets
`/freelance` - Browse available tasks""",
        inline=False
    )
    
    embed.add_field(
        name="⏱️ Work Hours Commands",
        value="""`/loghours` - Log your work hours
`/workreport` - Show your work hours report""",
        inline=False
    )
    
    embed.add_field(
        name="🪙 Obiz Coin Economy",
        value="""`/balance` - Check your coins
`/daily` - Claim daily reward
`/shop` - Spend your coins
`/transfer` - Send coins to others
`/refer` - Refer friends for bonuses""",
        inline=False
    )
    
    embed.add_field(
        name="🎰 Gambling Games",
        value="""`/coinflip` - Bet on heads or tails
`/dice` - Roll a dice
`/jackpot` - Join the jackpot""",
        inline=False
    )
    
    embed.add_field(
        name="📊 Stats & Leaderboards",
        value="""`/profile` - View your stats
`/leaderboard` - View leaderboards""",
        inline=False
    )
    
    embed.set_thumbnail(url="https://i.imgur.com/J5h8x2V.png")
    embed.set_footer(text="Premium Support System")
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✨ Legendary premium bot ready as {bot.user}")
    
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="tickets and Obiz Coins"
    )
    await bot.change_presence(activity=activity)
    check_reminders.start()
    update_active_users.start()
    check_jackpot.start()

@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    
    # Initialize user stats
    USER_STATS[str(member.id)] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
    
    # Assign Trainee role
    trainee_role = discord.utils.get(member.guild.roles, name="Trainee")
    if trainee_role:
        try:
            await member.add_roles(trainee_role)
        except:
            pass
    
    # Send welcome message
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        quote = random.choice(QUOTES)
        gif = random.choice(WELCOME_GIFS)
        
        embed = discord.Embed(
            title=f"✨ Welcome {member.display_name}!",
            description=quote,
            color=discord.Color.gold()
        )
        embed.set_image(url=gif)
        embed.set_footer(text="You've been awarded 🪙 1000 Obiz Coins to get started!")
        
        await welcome_channel.send(embed=embed)
        
        try:
            dm_embed = discord.Embed(
                title="🎉 Welcome to the Server!",
                description="Here's your starter pack to get you going:",
                color=discord.Color.green()
            )
            dm_embed.add_field(name="Obiz Coins", value="🪙 1000", inline=True)
            dm_embed.add_field(name="Starter Role", value="👶 Trainee", inline=True)
            dm_embed.add_field(name="First Steps", value="Use `/help` to see what you can do!", inline=False)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.attachments:
        return
    
    if message.reference:
        try:
            replied_message = await message.channel.fetch_message(message.reference.message_id)
            if replied_message.embeds and replied_message.embeds[0].title.startswith("🎫 Ticket #"):
                ticket_id = int(replied_message.embeds[0].footer.text.split(": ")[1])
                ticket = TICKETS_DB.get(ticket_id)
                if ticket:
                    ticket.attachments.extend([a.url for a in message.attachments])
                    
                    embed = discord.Embed(
                        description=f"📎 Added {len(message.attachments)} attachment(s) to ticket #{ticket_id}",
                        color=discord.Color.green()
                    )
                    await message.reply(embed=embed, delete_after=5)
                    
                    await replied_message.edit(embed=ticket.to_embed())
        except:
            pass

@tasks.loop(minutes=30)
async def check_reminders():
    now = datetime.now()
    for reminder in REMINDERS[:]:
        if now >= reminder["time"]:
            ticket = TICKETS_DB.get(reminder["ticket_id"])
            if ticket:
                user = bot.get_user(reminder["user_id"])
                if user:
                    embed = discord.Embed(
                        title=f"⏰ Reminder: Ticket #{ticket.id}",
                        description=f"**{ticket.title}**\n\n{reminder.get('note', 'No additional notes')}",
                        color=discord.Color.gold()
                    )
                    embed.add_field(name="Status", value=ticket.status, inline=True)
                    embed.add_field(name="Priority", value=ticket.priority, inline=True)
                    embed.add_field(name="Deadline", value=ticket.deadline, inline=True)
                    
                    try:
                        await user.send(embed=embed)
                        REMINDERS.remove(reminder)
                    except:
                        pass

@tasks.loop(minutes=15)
async def update_active_users():
    global ACTIVE_USERS
    
    # Check all guilds the bot is in
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            
            user_id = str(member.id)
            
            # Check if user is active (online, in voice, etc.)
            is_active = member.status != discord.Status.offline
            
            if is_active:
                if user_id not in ACTIVE_USERS:
                    ACTIVE_USERS[user_id] = {"last_active": datetime.now(), "hours_accumulated": 0}
                
                # Calculate time since last check
                time_since_last = (datetime.now() - ACTIVE_USERS[user_id]["last_active"]).total_seconds() / 3600
                ACTIVE_USERS[user_id]["hours_accumulated"] += time_since_last
                
                # Award coins if they've accumulated an hour
                if ACTIVE_USERS[user_id]["hours_accumulated"] >= 1:
                    hours = int(ACTIVE_USERS[user_id]["hours_accumulated"])
                    
                    if user_id not in USER_STATS:
                        USER_STATS[user_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
                    
                    coins_earned = hours * (2 if EVENT and EVENT["type"] == "Double Coins" else 1)
                    USER_STATS[user_id]["coins"] += coins_earned
                    USER_STATS[user_id]["xp"] += hours * 10
                    
                    # Reset accumulation
                    ACTIVE_USERS[user_id]["hours_accumulated"] -= hours
                
                # Update last active time
                ACTIVE_USERS[user_id]["last_active"] = datetime.now()
            else:
                # User is not active, reset their timer
                if user_id in ACTIVE_USERS:
                    del ACTIVE_USERS[user_id]

@tasks.loop(hours=24)
async def check_jackpot():
    global JACKPOT_POOL
    
    if JACKPOT_POOL["total"] > 0 and JACKPOT_POOL["participants"]:
        # Select a winner
        winner_id = random.choice(list(JACKPOT_POOL["participants"].keys()))
        winner_name = JACKPOT_POOL["participants"][winner_id]
        amount = JACKPOT_POOL["total"]
        
        # Award coins
        if winner_id not in USER_STATS:
            USER_STATS[winner_id] = {"coins": 1000, "streak": 0, "last_daily": None, "level": 1, "xp": 0, "badges": []}
        USER_STATS[winner_id]["coins"] += amount
        
        # Announce winner
        embed = discord.Embed(
            title="🎉 Jackpot Winner!",
            description=f"**{winner_name}** has won the jackpot of 🪙 {amount}!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://media.giphy.com/media/xUOxfjsW9fWPqEWouI/giphy.gif")
        
        for guild in bot.guilds:
            system_channel = guild.system_channel
            if system_channel:
                await system_channel.send(embed=embed)
        
        # Reset jackpot
        JACKPOT_POOL = {"total": 0, "participants": {}}

@bot.tree.command(name="event", description="🎪 Start a special event (Admin only)")
@app_commands.describe(event_type="Type of event to start")
@app_commands.choices(event_type=[
    app_commands.Choice(name="Double Coins", value="Double Coins"),
    app_commands.Choice(name="Hackathon", value="Hackathon"),
    app_commands.Choice(name="Ticket Blitz", value="Ticket Blitz")
])
async def start_event(interaction: discord.Interaction, event_type: app_commands.Choice[str]):
    global EVENT
    
    # Check admin permissions
    if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need admin privileges to start events",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    EVENT = {
        "type": event_type.value,
        "start_time": datetime.now(),
        "end_time": datetime.now() + timedelta(hours=24)
    }
    
    embed = discord.Embed(
        title="🎉 Event Started!",
        description=f"A **{event_type.value}** event has begun!",
        color=discord.Color.purple()
    )
    
    if event_type.value == "Double Coins":
        embed.add_field(name="Effect", value="Earn double Obiz Coins for all activities!", inline=False)
    elif event_type.value == "Hackathon":
        embed.add_field(name="Effect", value="Special bonuses for completing tickets quickly!", inline=False)
    elif event_type.value == "Ticket Blitz":
        embed.add_field(name="Effect", value="Increased rewards for creating and completing tickets!", inline=False)
    
    embed.add_field(name="Duration", value="24 hours", inline=False)
    await interaction.response.send_message(embed=embed)

bot.run(DISCORD_BOT_TOKEN)