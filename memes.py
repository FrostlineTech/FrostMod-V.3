from __future__ import annotations

import aiohttp
import discord
from discord import app_commands
from discord.app_commands import checks
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class MemesCog(commands.Cog):
    """Meme fun: fetch memes and create simple captioned embeds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="meme", description="Grab a random meme")
    @checks.cooldown(1, 5.0)  # 1 use per 5 seconds per user
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        title = "Random Meme"
        image_url = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme", headers={"User-Agent": "FrostMod (https://frostlinesolutions.com)"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        title = data.get("title") or title
                        image_url = data.get("url")
        except Exception:
            image_url = None
        embed = discord.Embed(title=title, color=BRAND_COLOR)
        if image_url:
            embed.set_image(url=image_url)
        else:
            embed.description = "Couldn't fetch a meme right now. Try again later."
        embed.set_footer(text=FOOTER_TEXT)
        view = discord.ui.View()
        if image_url:
            view.add_item(discord.ui.Button(label="Open", url=image_url))
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="caption", description="Create a simple captioned embed for an image (top;bottom)")
    @app_commands.describe(image_url="URL to the image", text="Caption text, format: top;bottom")
    @checks.cooldown(1, 10.0)  # avoid abuse
    async def caption(self, interaction: discord.Interaction, image_url: str, text: str):
        top, bottom = parse_caption(text)
        embed = discord.Embed(title=top or " ", description=bottom or None, color=BRAND_COLOR)
        embed.set_image(url=image_url)
        embed.set_footer(text=FOOTER_TEXT)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open", url=image_url))
        await interaction.response.send_message(embed=embed, view=view)


def parse_caption(text: str) -> tuple[str | None, str | None]:
    parts = [p.strip() for p in text.split(";")]
    if len(parts) == 0:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


async def setup(bot: commands.Bot):
    await bot.add_cog(MemesCog(bot))
