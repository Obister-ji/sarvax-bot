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
            
            embed = discord.Embed(
                title="⏱️ Work Hours Logged",
                description=f"Successfully recorded your work hours for {work_date.strftime('%d %b %Y')}",
                color=discord.Color.green()
            )
            embed.add_field(name="Start Time", value=str(self.start_time), inline=True)
            embed.add_field(name="End Time", value=str(self.end_time), inline=True)
            embed.add_field(name="Total Hours", value=f"{hours_worked} hours", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError as e:
            embed = discord.Embed(
                title="❌ Error Logging Hours",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

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

@bot.tree.command(name="help", description="ℹ️ Show premium bot help")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ Premium Ticket Bot Help",
        description="Manage support tickets and work hours with style!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🎫 Ticket Commands",
        value="""`/new` - Create a new ticket
`/ticket` - View a specific ticket
`/mytickets` - List your tickets""",
        inline=False
    )
    
    embed.add_field(
        name="⏱️ Work Hours Commands",
        value="""`/loghours` - Log your work hours
`/workreport` - Show your work hours report""",
        inline=False
    )
    
    embed.add_field(
        name="💎 Premium Features",
        value="""• Beautiful ticket management
• Work hour tracking
• Reminders and notifications
• File attachments
• And more!""",
        inline=False
    )
    
    embed.set_thumbnail(url="https://i.imgur.com/J5h8x2V.png")
    embed.set_footer(text="Premium Support System")
    
    await interaction.response.send_message(embed=embed)

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

bot.run(DISCORD_BOT_TOKEN)