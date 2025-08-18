#the point of this cog is to create a new command that a user (Not admin bound) can use to get Webstatus From Https://frostlinesolutions.com
#the command will be /webstatus
#make sure to follow the branding.py file to ensure the embeds say powered by FSLLC / FrostlineSolutions.com at the bottom of the embed in the footer

from __future__ import annotations

import asyncio
from time import perf_counter
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED


URL = "https://frostlinesolutions.com"


class Webserver(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    @app_commands.command(name="webstatus", description="Check frostlinesolutions.com status and response time")
    async def webstatus(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        t0 = perf_counter()
        status: int | None = None
        ok = False
        error: str | None = None
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=8)
            async with session.get(URL, timeout=timeout, allow_redirects=True) as resp:
                status = resp.status
                ok = 200 <= resp.status < 400
                # drain small content to fully complete request (not strictly necessary)
                await resp.read()
        except asyncio.TimeoutError:
            error = "Request timed out"
        except Exception as e:
            error = str(e)
        t1 = perf_counter()
        ms = int((t1 - t0) * 1000)

        # Color logic
        if not ok:
            color = RED
        else:
            color = GREEN if ms < 800 else YELLOW

        title = "Website Status"
        desc = f"URL: {URL}"
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="HTTP Status", value=str(status) if status is not None else "N/A", inline=True)
        embed.add_field(name="Response Time", value=f"{ms} ms", inline=True)
        embed.add_field(name="Reachable", value="Yes" if ok else "No", inline=True)
        if error:
            embed.add_field(name="Error", value=error[:1000], inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, ephemeral=True)

    def cog_unload(self) -> None:
        # Close our session if we created one
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())


async def setup(bot: commands.Bot) -> None:
    cog = Webserver(bot)
    await bot.add_cog(cog)
    try:
        # Register the slash command
        bot.tree.add_command(cog.webstatus)
    except Exception:
        # If it's already added due to reloads
        pass
