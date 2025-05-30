import discord
from discord.ext import commands
from discord.utils import get
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

LOG_CHANNEL_ID = 1263131319672504400  # Vervang met jouw log kanaal ID
WELCOME_ROLE_ID = 1263132430663942185  # Rol voor nieuwe leden

# Infractions geheugen (hernoemd)
infractions_data = {}

# Helper functie om een mooie embed te maken voor logs
def create_log_embed(title, description, user: discord.Member = None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    if user:
        embed.set_author(name=str(user), icon_url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(text=f"User ID: {user.id}")
    else:
        embed.set_footer(text="")
    return embed

async def log_embed(embed):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f'{bot.user} is online')

# 1. Welkomstbericht met embed (zonder afbeelding)
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        embed = discord.Embed(
            title="Welkom!",
            description=f"Welkom {member.mention} op de server!",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)

    role = member.guild.get_role(WELCOME_ROLE_ID)
    if role:
        await member.add_roles(role)

    embed_log = create_log_embed(
        title="Nieuwe gebruiker",
        description=f"{member.mention} is lid geworden.",
        user=member
    )
    await log_embed(embed_log)

@bot.event
async def on_member_remove(member):
    embed = create_log_embed(
        title="Lid vertrokken",
        description=f"{member} heeft de server verlaten.",
        user=member
    )
    await log_embed(embed)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        removed = [r for r in before.roles if r not in after.roles]
        added = [r for r in after.roles if r not in before.roles]
        if added:
            embed = create_log_embed(
                title="Rol toegevoegd",
                description=f"Rol(len) {', '.join(r.name for r in added)} toegevoegd aan {after.mention}.",
                user=after
            )
            await log_embed(embed)
        if removed:
            embed = create_log_embed(
                title="Rol verwijderd",
                description=f"Rol(len) {', '.join(r.name for r in removed)} verwijderd van {after.mention}.",
                user=after
            )
            await log_embed(embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    embed = create_log_embed(
        title="Bericht verwijderd",
        description=f"In kanaal {message.channel.mention} is het bericht verwijderd:\n\n{message.content}",
        user=message.author
    )
    await log_embed(embed)

# 10. Logging van message edits
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    if before.content == after.content:
        return  # Geen echte wijziging
    embed = create_log_embed(
        title="Bericht aangepast",
        description=(
            f"In kanaal {before.channel.mention} is een bericht aangepast door {before.author.mention}.\n\n"
            f"**Oud bericht:**\n{before.content}\n\n"
            f"**Nieuw bericht:**\n{after.content}"
        ),
        user=before.author
    )
    await log_embed(embed)

# Moderatie commands, inclusief nieuwe

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'{member} is gekickt.')
    embed = create_log_embed(
        title="Kick",
        description=f"{ctx.author.mention} heeft {member.mention} gekickt.\nReden: {reason or 'Geen reden opgegeven'}",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f'{member} is geband.')
    embed = create_log_embed(
        title="Ban",
        description=f"{ctx.author.mention} heeft {member.mention} geband.\nReden: {reason or 'Geen reden opgegeven'}",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member):
    mute_role = get(ctx.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(mute_role, speak=False, send_messages=False)
    await member.add_roles(mute_role)
    await ctx.send(f'{member} is gemute.')
    embed = create_log_embed(
        title="Mute",
        description=f"{ctx.author.mention} heeft {member.mention} gemute.",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    mute_role = get(ctx.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f'{member} is geunmute.')
        embed = create_log_embed(
            title="Unmute",
            description=f"{ctx.author.mention} heeft {member.mention} geunmute.",
            user=ctx.author
        )
        await log_embed(embed)

# 4. Infractions systeem + warn command

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason=None):
    user_id = member.id
    if user_id not in infractions_data:
        infractions_data[user_id] = []
    infractions_data[user_id].append({
        'type': 'warn',
        'reason': reason or "Geen reden opgegeven",
        'moderator': ctx.author.id,
        'time': datetime.now(timezone.utc)
    })
    await ctx.send(f'{member.mention} is gewaarschuwd. Reden: {reason or "Geen reden opgegeven"}')
    embed = create_log_embed(
        title="Warn",
        description=f"{ctx.author.mention} heeft {member.mention} gewaarschuwd.\nReden: {reason or 'Geen reden opgegeven'}",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def infractions(ctx, member: discord.Member):
    user_id = member.id
    if user_id not in infractions_data or not infractions_data[user_id]:
        await ctx.send(f"{member} heeft geen waarschuwingen of straffen.")
        return
    embed = discord.Embed(title=f"Infractions voor {member}", color=discord.Color.red())
    for i, inf in enumerate(infractions_data[user_id], 1):
        mod = bot.get_user(inf['moderator'])
        embed.add_field(
            name=f"{i}. {inf['type'].capitalize()}",
            value=(
                f"Reden: {inf['reason']}\n"
                f"Moderator: {mod} ({inf['moderator']})\n"
                f"Tijd: {inf['time'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
            ),
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f'{len(deleted)} berichten verwijderd.', delete_after=5)
    embed = create_log_embed(
        title="Berichten verwijderd",
        description=f"{ctx.author.mention} heeft {len(deleted)} berichten verwijderd in {ctx.channel.mention}.",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def giveroleall(ctx, role: discord.Role):
    for member in ctx.guild.members:
        if role not in member.roles:
            await member.add_roles(role)
    await ctx.send(f'Alle leden hebben nu de rol {role.name} gekregen.')
    embed = create_log_embed(
        title="Role aan iedereen gegeven",
        description=f"{ctx.author.mention} gaf de rol {role.name} aan alle leden.",
        user=ctx.author
    )
    await log_embed(embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def removeroleall(ctx, role: discord.Role):
    for member in ctx.guild.members:
        if role in member.roles:
            await member.remove_roles(role)
    await ctx.send(f'Rol {role.name} is van alle leden verwijderd.')
    embed = create_log_embed(
        title="Role van iedereen verwijderd",
        description=f"{ctx.author.mention} verwijderde de rol {role.name} van alle leden.",
        user=ctx.author
    )
    await log_embed(embed)

# 3. Slowmode command
@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f'Slowmode ingesteld op {seconds} seconden.')

# 1. Userinfo command
@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Info van {member}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Gebruikersnaam", value=str(member), inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Account gemaakt", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Lid sinds", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Aantal rollen", value=len(member.roles) - 1, inline=True)  # -1 want @everyone
    await ctx.send(embed=embed)

# 2. Serverinfo command
@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Serverinfo: {guild.name}", color=discord.Color.gold())
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Lid sinds", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Aantal leden", value=guild.member_count, inline=True)
    embed.add_field(name="Aantal kanalen", value=len(guild.channels), inline=True)
    embed.add_field(name="Eigenaar", value=str(guild.owner), inline=True)
    await ctx.send(embed=embed)

# 5. Avatar command
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Avatar van {member}", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)


# 6. Help command met embed overzicht
@bot.command()
async def info(ctx):
    embed = discord.Embed(title="Help - Overzicht van commands", color=discord.Color.purple())
    embed.add_field(name="!kick @gebruiker [reden]", value="Kick een gebruiker van de server.", inline=False)
    embed.add_field(name="!ban @gebruiker [reden]", value="Ban een gebruiker van de server.", inline=False)
    embed.add_field(name="!mute @gebruiker", value="Mute een gebruiker.", inline=False)
    embed.add_field(name="!unmute @gebruiker", value="Unmute een gebruiker.", inline=False)
    embed.add_field(name="!warn @gebruiker [reden]", value="Waarschuw een gebruiker.", inline=False)
    embed.add_field(name="!infractions @gebruiker", value="Bekijk de waarschuwingen en straffen van een gebruiker.", inline=False)
    embed.add_field(name="!clear [aantal]", value="Verwijder aantal berichten.", inline=False)
    embed.add_field(name="!slowmode [seconden]", value="Stel slowmode in voor het kanaal.", inline=False)
    embed.add_field(name="!giveroleall @rol", value="Geef een rol aan alle leden.", inline=False)
    embed.add_field(name="!removeroleall @rol", value="Verwijder een rol van alle leden.", inline=False)
    embed.add_field(name="!userinfo [@gebruiker]", value="Bekijk informatie over een gebruiker.", inline=False)
    embed.add_field(name="!serverinfo", value="Bekijk informatie over de server.", inline=False)
    embed.add_field(name="!avatar [@gebruiker]", value="Bekijk de avatar van een gebruiker.", inline=False)
    await ctx.send(embed=embed)

bot.run('DISCORD_BOT_TOKEN')