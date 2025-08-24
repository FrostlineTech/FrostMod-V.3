from __future__ import annotations

import logging
import discord
from discord.ext import commands
from discord import app_commands

from branding import BRAND_COLOR, GREEN, YELLOW, RED, FOOTER_TEXT
from ui import make_embed


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))
        # Also attach as a global tree error handler to catch errors from checks
        # like cooldowns before command body runs.
        bot.tree.on_error = self.on_tree_error  # type: ignore[assignment]

    async def on_tree_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle(interaction, error)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self._handle(interaction, error)

    async def _handle(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Unwrap
        err = getattr(error, 'original', error)
        title = "Something went wrong"
        desc = ""
        color = RED

        try:
            if isinstance(err, app_commands.MissingPermissions):
                title = "Missing permissions"
                perms = ", ".join(err.missing_permissions)
                desc = f"You are missing: {perms}"
                color = YELLOW
            elif isinstance(err, app_commands.BotMissingPermissions):
                title = "I am missing permissions"
                perms = ", ".join(err.missing_permissions)
                desc = f"Grant me: {perms} in this channel."
                color = YELLOW
            elif isinstance(err, app_commands.CommandOnCooldown):
                title = "Slow down"
                desc = f"Try again in {err.retry_after:.1f}s"
                color = YELLOW
            elif isinstance(err, app_commands.CheckFailure):
                title = "Action not allowed"
                desc = "You can't use this command here or now."
                color = YELLOW
            elif isinstance(err, app_commands.TransformerError):
                title = "Invalid input"
                desc = "One or more options were invalid."
                color = YELLOW
            else:
                title = "Unexpected error"
                desc = "An unexpected error occurred. The incident has been logged."
                color = RED
        except Exception:
            pass

        # Log stack
        self.log.exception("App command error: %s", err)

        try:
            embed = make_embed(title=title, description=desc or None, interaction=interaction, color=color)
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            try:
                # Last resort plain text
                content = f"{title}: {desc}" if desc else title
                if interaction.response.is_done():
                    await interaction.followup.send(content, ephemeral=True)
                else:
                    await interaction.response.send_message(content, ephemeral=True)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
