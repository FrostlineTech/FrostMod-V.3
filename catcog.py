from __future__ import annotations

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class CatCog(commands.Cog):
    """Provides /cat to post a random cat image."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cat", description="Get a random cat image")
    async def cat(self, interaction: discord.Interaction):
        url: str | None = None
        # Use TheCatAPI (no key required for basic usage)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search", timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and data:
                            url = data[0].get("url")
        except Exception as e:
            # Log and continue to error message below
            self.bot.log.warning(f"/cat fetch failed: {e}")

        if not url:
            await interaction.response.send_message("Couldn't fetch a cat right now. Please try again later.", ephemeral=True)
            return

        embed = discord.Embed(title="Random Cat", color=BRAND_COLOR)
        embed.set_image(url=url)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CatCog(bot))

