import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio

# ==============================================================================
# CONFIGURATION
# ==============================================================================
TOKEN = "TOKENNNHEREEE" 

# ID of the role to ping when a ticket is opened (e.g. SupportAdmins)
# REPLACE THIS WITH THE ACTUAL ROLE ID FROM YOUR SERVER
SUPPORT_ROLE_ID = 000000000000000000 

# Global dictionary to track active disconnect timers
disconnect_tasks = {}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_next_ticket_number(guild):
    """
    Scans 'Life Support Tickets' and 'Closed Tickets' to find the next available number.
    """
    cats = [
        discord.utils.get(guild.categories, name="Life Support Tickets"), 
        discord.utils.get(guild.categories, name="Closed Tickets")
    ]
    numbers = []
    for cat in cats:
        if cat:
            for channel in cat.channels:
                # Checks for format 'ticket-0000'
                if channel.name.startswith("ticket-") and channel.name[7:].isdigit():
                    numbers.append(int(channel.name[7:]))
    
    if not numbers:
        return 1
    return max(numbers) + 1

# ==============================================================================
# TICKET SYSTEM UI
# ==============================================================================

# We define CloseTicketView first so it is definitely available
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close & Archive", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        
        await interaction.response.send_message("Archiving ticket...")
        
        # 1. Get or Create 'Closed Tickets' Category
        closed_category = discord.utils.get(guild.categories, name="Closed Tickets")
        if not closed_category:
            # Create it privately
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            if SUPPORT_ROLE_ID != 0:
                support_role = guild.get_role(SUPPORT_ROLE_ID)
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(read_messages=True)
            
            closed_category = await guild.create_category("Closed Tickets", overwrites=overwrites)

        # 2. Move Channel and Sync Permissions
        await channel.edit(category=closed_category, sync_permissions=True)
        
        # 3. Notify inside the channel
        embed = discord.Embed(description="🔒 **Ticket Closed and Archived.**", color=discord.Color.red())
        await channel.send(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open a Life Support Ticket", style=discord.ButtonStyle.green, emoji="🎟", custom_id="ticket_create_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        
        # 1. Get or Create Category
        category = discord.utils.get(guild.categories, name="Life Support Tickets")
        if not category:
            category = await guild.create_category("Life Support Tickets")

        # 2. Determine Channel Name
        next_num = get_next_ticket_number(guild)
        channel_name = f"ticket-{next_num:04d}"

        # 3. Set Permissions
        # We give the bot extra permissions (embed_links) to ensure it can post the menu
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True)
        }

        support_role_mention = ""
        if SUPPORT_ROLE_ID != 0:
            support_role = guild.get_role(SUPPORT_ROLE_ID)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                support_role_mention = support_role.mention

        # 4. Create Channel
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        await interaction.response.send_message(f"Your Life Support ticket has been opened: {ticket_channel.mention}", ephemeral=True)
        
        # 5. Send Ticket Message
        embed = discord.Embed(
            title=f"Life Support #{next_num:04d}", 
            description="Please describe your issue. Support will be with you shortly.", 
            color=discord.Color.green()
        )
        
        content_msg = f"{interaction.user.mention} {support_role_mention}".strip()
        
        # Wrapped in try/except to catch errors if the message fails to send
        try:
            await ticket_channel.send(content=content_msg, embed=embed, view=CloseTicketView())
        except Exception as e:
            print(f"ERROR SENDING TICKET EMBED: {e}")
            await ticket_channel.send(f"Ticket created, but I couldn't load the menu. Error: {e}")

# ==============================================================================
# MAIN BOT CLASS
# ==============================================================================
class LifeGiverBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketView())
        self.add_view(CloseTicketView())
        self.status_loop.start()
        print("Setup complete. Waiting for commands...")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('Life Giver is active in Life Lounge.')

    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel:
            embed = discord.Embed(
                title="New Life Has Entered!",
                description=f"Welcome to **Life Lounge**, {member.mention}! We are glad you are here.",
                color=discord.Color.teal()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

    @tasks.loop(seconds=30)
    async def status_loop(self):
        activities = [
            discord.Activity(type=discord.ActivityType.watching, name="Life Lounge"),
            discord.Game("Giving Life")
        ]
        for activity in activities:
            await self.change_presence(activity=activity)
            await asyncio.sleep(30)

client = LifeGiverBot()

# ==============================================================================
# COMMANDS
# ==============================================================================

@client.command()
async def sync(ctx):
    try:
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        fmt = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.message.delete()
        await ctx.send(f"✅ **Synced {len(fmt)} commands** to this server! You should see them now.")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync: {e}")
        
@client.command(name="ping")
async def ping(ctx):
    latency = round(client.latency * 1000)
    await ctx.send(f"🏓 **Pong!** Connection latency is {latency}ms.")

@client.command(name="say")
async def say(ctx, *, message):
    if ctx.author.guild_permissions.administrator:
        await ctx.message.delete() 
        await ctx.send(message)
    else:
        await ctx.send("❌ You need Administration permission for this.", delete_after=5)

@client.command(name="avatar")
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.purple())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

# SLASH COMMANDS
@client.tree.command(name="disconnect", description="Disconnect a user from Voice after a specific time.")
@app_commands.describe(member="Who to disconnect", seconds="Seconds to wait", minutes="Minutes to wait")
async def disconnect(interaction: discord.Interaction, member: discord.Member, seconds: int = 0, minutes: int = 0):
    is_admin = interaction.user.guild_permissions.administrator
    is_self = interaction.user.id == member.id

    if not is_self and not is_admin:
        return await interaction.response.send_message("🚫 You can only disconnect yourself. Ask an Admin to disconnect others.", ephemeral=True)

    if not member.voice:
        return await interaction.response.send_message(f"{member.name} is not in a voice channel.", ephemeral=True)

    total_seconds = seconds + (minutes * 60)
    if total_seconds <= 0:
        return await interaction.response.send_message("Please provide a valid time.", ephemeral=True)

    if member.id in disconnect_tasks:
        try:
            disconnect_tasks[member.id].cancel()
        except Exception:
            pass
        del disconnect_tasks[member.id]

    async def perform_disconnect():
        try:
            await asyncio.sleep(total_seconds)
            if member.voice:
                await member.move_to(None)
                try:
                    await interaction.channel.send(f"✅ **{member.name}** has been disconnected (Timer Reached).")
                except:
                    pass
        except asyncio.CancelledError:
            pass 
        except Exception as e:
            print(f"Error disconnecting {member.name}: {e}")
        finally:
            if member.id in disconnect_tasks:
                del disconnect_tasks[member.id]

    task = asyncio.create_task(perform_disconnect())
    disconnect_tasks[member.id] = task

    embed = discord.Embed(
        title="⏳ Timer Set", 
        description=f"Disconnecting **{member.name}** in **{total_seconds}** seconds.\nUse `/cancel` to stop.", 
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="cancel", description="Cancel an active disconnect timer.")
@app_commands.describe(member="Who to cancel the timer for")
async def cancel(interaction: discord.Interaction, member: discord.Member):
    is_admin = interaction.user.guild_permissions.administrator
    is_self = interaction.user.id == member.id

    if not is_self and not is_admin:
        return await interaction.response.send_message("🚫 You can only cancel your own timers.", ephemeral=True)

    if member.id in disconnect_tasks:
        task = disconnect_tasks[member.id]
        task.cancel()
        del disconnect_tasks[member.id]
        await interaction.response.send_message(f"✅ Cancelled the disconnect timer for **{member.name}**.")
    else:
        await interaction.response.send_message(f"❌ No active timer found for **{member.name}**.", ephemeral=True)

@client.tree.command(name="setup_tickets", description="Spawns the Ticket System Panel")
async def setup_tickets(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admins only.", ephemeral=True)
    
    embed = discord.Embed(
        title="Life Lounge Support", 
        description="Click the button to get direct help from moderators.",
        color=discord.Color.green()
    )
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("Ticket panel created!", ephemeral=True)

@client.tree.command(name="clean", description="Cleans messages from the chat.")
@app_commands.describe(amount="Number of messages to delete")
async def clean(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("You cannot manage messages.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True) 
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Swept away {len(deleted)} messages.", ephemeral=True)

client.run(TOKEN)