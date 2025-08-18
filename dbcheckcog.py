#this is where the logic for /db will be stored this is so admin can check if the database is working 
#display ping and database name

from __future__ import annotations

import os
from time import perf_counter

import discord
from discord import app_commands
from discord.ext import commands

from branding import GREEN, YELLOW, RED, FOOTER_TEXT


class DBCheck(commands.Cog):
    """Admin-only database connectivity check."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="db", description="Check database connectivity and latency (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def dbcheck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        pool = getattr(self.bot, "pool", None)
        if not pool:
            embed = discord.Embed(title="Database Status", description="Database not configured.", color=YELLOW)
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        try:
            t0 = perf_counter()
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
            t1 = perf_counter()
            db_ms = int((t1 - t0) * 1000)
            color = GREEN if db_ms < 50 else YELLOW if db_ms < 150 else RED
            db_name = os.getenv("DB_NAME") or "(unknown)"
            embed = discord.Embed(title="Database Status", color=color)
            embed.add_field(name="Ping", value=f"{db_ms} ms", inline=True)
            embed.add_field(name="Database", value=db_name, inline=True)
            embed.add_field(name="Pool", value="connected", inline=True)
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.bot.log.warning(f"[DB] Health check failed: {e}")
            embed = discord.Embed(title="Database Status", description=f"Error: {e}", color=RED)
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(DBCheck(bot))