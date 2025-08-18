#serverinfo cog to check the server info 
#display server name, id, member count, and boost count, channel count, role count, emoji count, server age, owner
#command /serverinfo
#ensure commmand is registered in frostmodv3.py it is all member based 

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from datetime import timezone

from branding import BRAND_COLOR, FOOTER_TEXT


class ServerInfo(commands.Cog):
    """Provides /serverinfo for members."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="Show information about this server")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        assert guild is not None

        # Basic fields
        name = guild.name
        gid = guild.id
        member_count = guild.member_count or 0
        boosts = getattr(guild, "premium_subscription_count", 0) or 0
        roles = len(guild.roles)
        emojis = len(guild.emojis)
        channels = len(guild.channels)
        created_at = guild.created_at
        # Convert to aware UTC for format_dt
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        owner = None
        try:
            owner = guild.owner or (await guild.fetch_owner())
        except Exception:
            owner = None

        embed = discord.Embed(title=f"Server Info — {name}", color=BRAND_COLOR)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="ID", value=str(gid), inline=True)
        embed.add_field(name="Owner", value=f"{owner.mention} ({owner})" if owner else "Unknown", inline=False)
        embed.add_field(name="Members", value=str(member_count), inline=True)
        embed.add_field(name="Boosts", value=str(boosts), inline=True)
        embed.add_field(name="Channels", value=str(channels), inline=True)
        embed.add_field(name="Roles", value=str(roles), inline=True)
        embed.add_field(name="Emojis", value=str(emojis), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(created_at, style="F"), inline=False)
        embed.set_footer(text=FOOTER_TEXT)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerInfo(bot))