from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT
from ui import make_embed


ABOUT_TEXT = (
    "FrostMod is a modern moderation and utility bot focused on clear logs, AI-powered moderation, and helpful server tools — with fun extras (mini games and memes).\n\n"
    "Features: Advanced AI moderation with channel-specific settings, user profiling with risk assessment, pattern recognition for content split across messages, "
    "and an AI assistant that can answer questions about your server.\n\n"
    "Privacy: Only configured items are logged (see /logs). We store lightweight server config and activity metrics to improve features like /activity. "
    "User profiling data is used only for authorized risk assessments and AI functionality. No message content is stored beyond what is necessary for logs you explicitly enable.\n\n"
    "Support: frostlinesolutions.com — Powered by Frostline Solutions LLC."
)

MEMBER_COMMANDS = [
    ("/serverinfo", "Show server stats (name, members, boosts, channels, roles)."),
    ("/webstatus", "Check frostlinesolutions.com response and uptime color."),
    ("/activity", "View your or another user's activity with period filters."),
    ("/avatar", "Show a user's avatar with quick Open/Copy ID buttons."),
    ("/banner", "Show a user's banner if available."),
    ("/userinfo", "Compact profile summary: ID, created, joined, roles."),
    ("/ask", "Ask the AI assistant a question about the server."),
    ("/askabout", "Ask about a specific topic with context-aware responses."),
    ("/aiexplain", "Learn how AI moderation works in detail."),
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
        embed = make_embed(title="About FrostMod", description=ABOUT_TEXT, color=BRAND_COLOR, interaction=interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="commands", description="List common member commands with tips")
    async def commands_list(self, interaction: discord.Interaction):
        embed = make_embed(title="Member Commands", color=BRAND_COLOR, interaction=interaction)
        for name, desc in MEMBER_COMMANDS:
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PublicInfo(bot))
