#support.py
#this cog will be used to create a new command that a user (Not admin bound) can use to get support from the bot
#the command will be /support

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT

SUPPORT_INVITE = "https://discord.gg/FGUEEj6k7k"


class SupportView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.add_item(
            discord.ui.Button(
                label="Join Support Server",
                style=discord.ButtonStyle.link,
                url=SUPPORT_INVITE,
            )
        )


class Support(commands.Cog):
    """Public support command for users to reach the official support server."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="support", description="Get help in the official support server")
    async def support(self, interaction: discord.Interaction) -> None:
        """Send an embed with a button to the support server invite."""
        embed = discord.Embed(
            title="FrostMod Support",
            description=(
                "Need assistance or have feedback? Click the button below to join our official support server.\n\n"
                f"Invite: {SUPPORT_INVITE}"
            ),
            color=BRAND_COLOR,
        )
        embed.set_footer(text=FOOTER_TEXT)
        view = SupportView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Support(bot))