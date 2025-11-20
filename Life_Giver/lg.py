import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio

# ==============================================================================
# CONFIGURATION
# ==============================================================================
TOKEN = "TOKENHERE" 

# ID of the role to ping when a ticket is opened
SUPPORT_ROLE_ID = 000000000000000000 

# ==============================================================================
# TICKET SYSTEM UI
# ==============================================================================
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Life Support", style=discord.ButtonStyle.green, emoji="🆘", custom_id="ticket_create_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Life Support Tickets")
        
        if not category:
            category = await guild.create_category("Life Support Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        if SUPPORT_ROLE_ID != 0:
            support_role = guild.get_role(SUPPORT_ROLE_ID)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)

        await interaction.response.send_message(f"Your Life Support channel has been opened: {ticket_channel.mention}", ephemeral=True)
        
        embed = discord.Embed(title="Life Support", description="Describe your issue. Staff will be with you shortly.", color=discord.Color.green())
        await ticket_channel.send(content=f"{interaction.user.mention}", embed=embed, view=CloseTicketView())

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing this ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# ==============================================================================
# MAIN BOT CLASS
# ==============================================================================
class LifeGiverBot(commands.Bot):
    def __init__(self):
        # Enable all necessary intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        # We set a command_prefix to "!" so normal commands work
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketView())
        self.add_view(CloseTicketView())
        # Start the background status loop
        self.status_loop.start()
        print("Setup complete. Waiting for commands...")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('Life Giver is active in Life Lounge.')
        print('If slash commands are missing, type "!sync" in your server chat.')

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
# PREFIX COMMANDS (Traditional !commands)
# ==============================================================================

@client.command()
async def sync(ctx):
    """Syncs slash commands to the current server instantly."""
    try:
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        fmt = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ **Synced {len(fmt)} commands** to this server! You should see them now.")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync: {e}")

@client.command(name="ping")
async def ping(ctx):
    """Check if the bot is alive and check latency."""
    latency = round(client.latency * 1000)
    await ctx.send(f"🏓 **Pong!** Connection latency is {latency}ms.")

@client.command(name="say")
async def say(ctx, *, message):
    """Make the bot say something (Admins/Mods only)."""
    # Check if user has permission to manage messages
    if ctx.author.guild_permissions.manage_messages:
        await ctx.message.delete() # Delete the command message so it looks like the bot spoke naturally
        await ctx.send(message)
    else:
        await ctx.send("❌ You need 'Manage Messages' permission for this.", delete_after=5)

@client.command(name="avatar")
async def avatar(ctx, member: discord.Member = None):
    """Displays a big version of a user's avatar."""
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.purple())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

# ==============================================================================
# SLASH COMMANDS (Modern /commands)
# ==============================================================================

@client.tree.command(name="disconnect_timer", description="Disconnect a user from Voice after a specific time.")
@app_commands.describe(member="Who to disconnect", seconds="Seconds to wait", minutes="Minutes to wait")
async def disconnect_timer(interaction: discord.Interaction, member: discord.Member, seconds: int = 0, minutes: int = 0):
    if not interaction.user.guild_permissions.move_members:
        return await interaction.response.send_message("You lack the 'Move Members' permission.", ephemeral=True)
    
    total_seconds = seconds + (minutes * 60)
    if total_seconds <= 0:
        return await interaction.response.send_message("Please provide a valid time.", ephemeral=True)

    if not member.voice:
        return await interaction.response.send_message(f"{member.name} is not in a voice channel.", ephemeral=True)

    embed = discord.Embed(title="⏳ Timer Set", description=f"Disconnecting **{member.name}** in **{total_seconds}** seconds.", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

    await asyncio.sleep(total_seconds)

    if member.voice:
        try:
            await member.move_to(None)
            await interaction.followup.send(f"✅ **{member.name}** has been disconnected.")
        except discord.Forbidden:
            await interaction.followup.send("❌ I tried to disconnect them, but I lost permission!")
    else:
        await interaction.followup.send(f"ℹ️ **{member.name}** left the voice channel before the timer ended.")

@client.tree.command(name="setup_tickets", description="Spawns the Ticket System Panel")
async def setup_tickets(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admins only.", ephemeral=True)
    
    embed = discord.Embed(
        title="Life Lounge Support", 
        description="Click the button below to speak privately with the staff.",
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