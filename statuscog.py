from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from branding import GREEN, YELLOW, RED, FOOTER_TEXT


def format_timedelta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


class Status(commands.Cog):
    """Show bot uptime and latency."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="status", description="Show bot uptime and API latency")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ws_ms = int((self.bot.latency or 0) * 1000)
        color = GREEN if ws_ms < 250 else YELLOW if ws_ms < 600 else RED
        embed = discord.Embed(title="Bot Status", color=color)
        # Uptime
        start_time = getattr(self.bot, "start_time", None)
        if start_time is not None:
            delta = discord.utils.utcnow() - start_time
            embed.add_field(name="Uptime", value=format_timedelta(delta), inline=True)
            embed.add_field(name="Online Since", value=discord.utils.format_dt(start_time, style="F"), inline=True)
        embed.add_field(name="WebSocket Latency", value=f"{ws_ms} ms", inline=True)
        if interaction.guild:
            embed.add_field(name="Guild", value=interaction.guild.name, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))

