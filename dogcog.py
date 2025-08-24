from __future__ import annotations

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class DogCog(commands.Cog):
    """Provides /dog to post a random dog image."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dog", description="Get a random dog image")
    async def dog(self, interaction: discord.Interaction):
        url: str | None = None
        # Use Dog CEO API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random", timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get("status") == "success":
                            url = data.get("message")
        except Exception as e:
            self.bot.log.warning(f"/dog fetch failed: {e}")

        if not url:
            await interaction.response.send_message("Couldn't fetch a dog right now. Please try again later.", ephemeral=True)
            return

        embed = discord.Embed(title="Random Dog", color=BRAND_COLOR)
        embed.set_image(url=url)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DogCog(bot))

