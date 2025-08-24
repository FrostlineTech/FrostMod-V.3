from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


ABOUT_TEXT = (
    "FrostMod is a modern moderation and utility bot focused on clear logs, simple setup, and helpful server tools — with fun extras (mini games and memes).\n\n"
    "Privacy: Only configured items are logged (see /logs). We store lightweight server config and activity metrics to improve features like /activity. "
    "No message content is stored beyond what is necessary for logs you explicitly enable.\n\n"
    "Support: frostlinesolutions.com — Powered by Frostline Solutions LLC."
)

MEMBER_COMMANDS = [
    ("/serverinfo", "Show server stats (name, members, boosts, channels, roles)."),
    ("/webstatus", "Check frostlinesolutions.com response and uptime color."),
    ("/activity", "View your or another user's activity with period filters."),
    ("/avatar", "Show a user's avatar with quick Open/Copy ID buttons."),
    ("/banner", "Show a user's banner if available."),
    ("/userinfo", "Compact profile summary: ID, created, joined, roles."),
    ("/rps", "Play Rock-Paper-Scissors vs the bot (buttons)."),
    ("/tictactoe", "Challenge a member to TicTacToe (buttons)."),
    ("/connect4", "Challenge a member to Connect 4 (buttons)."),
    ("/meme", "Grab a random meme."),
    ("/caption", "Create a simple captioned image: top;bottom."),
    ("/dadjoke", "Get a random dad joke."),
]


class PublicInfo(commands.Cog):
    """Public info commands: /about and /commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="about", description="About FrostMod: features, privacy, and support info")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(title="About FrostMod", description=ABOUT_TEXT, color=BRAND_COLOR)
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="commands", description="List common member commands with tips")
    async def commands_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Member Commands", color=BRAND_COLOR)
        for name, desc in MEMBER_COMMANDS:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PublicInfo(bot))
