#this file is meant to be a cog for random dad jokes 
#ensure this cog and command is loaded in the main file frostmodv3.py   
#the command will be /dadjoke 
#make sure to follow the branding.py file to ensure the embeds say powered by FSLLC / FrostlineSolutions.com at the bottom of the embed in the footer

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class DadJokeCog(commands.Cog):
    """Provides a simple /dadjoke command for a random dad joke."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dadjoke", description="Get a random dad joke")
    async def dadjoke(self, interaction: discord.Interaction):
        await interaction.response.defer()
        joke_text = None
        # Fetch from icanhazdadjoke (no API key required)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json", "User-Agent": "FrostMod (https://frostlinesolutions.com)"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        joke_text = data.get("joke")
        except Exception:
            joke_text = None

        if not joke_text:
            joke_text = "I tried to tell a joke, but it didn't fetch. Try again!"

        embed = discord.Embed(title="Dad Joke", description=joke_text, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DadJokeCog(bot))