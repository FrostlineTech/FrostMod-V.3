import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from branding import BRAND_COLOR, FOOTER_TEXT


class PurgeCog(commands.Cog):
    """Cog for administrative purge operations."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="purge", description="Delete a number of recent messages in this channel (admin only).")
    @app_commands.describe(amount="Number of recent messages to delete (1-200)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 200]):
        # Ensure the command is used in a text channel in a guild
        if interaction.guild is None or not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("This command can only be used in a server text channel.", ephemeral=True)
            return

        channel = interaction.channel

        # Acknowledge quickly to avoid the 3s interaction timeout
        await interaction.response.defer(ephemeral=False, thinking=True)

        # Try bulk deletion. Note: Only messages under 14 days old are bulk-deletable.
        deleted = []
        reason = f"Purged by {interaction.user} via /purge"
        try:
            # Use built-in purge which handles rate limits internally
            # limit includes the command invocation; since this is an interaction, it's not a message yet
            if isinstance(channel, discord.TextChannel):
                deleted = await channel.purge(limit=amount, bulk=True, reason=reason)
            elif isinstance(channel, discord.Thread):
                # Threads don't support bulk=True; fall back to manual delete
                async for msg in channel.history(limit=amount):
                    try:
                        await msg.delete()
                        deleted.append(msg)
                        await asyncio.sleep(0.2)  # gentle pacing to avoid hitting rate limits
                    except discord.HTTPException:
                        pass
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to manage messages here.")
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to purge messages: {e}")
            return

        count = len(deleted)
        embed = discord.Embed(
            title="Purge Complete",
            description=f"Deleted {count} message(s) in {channel.mention}.",
            color=BRAND_COLOR,
        )
        embed.set_footer(text=FOOTER_TEXT)

        # Ephemeral ack to the invoker
        try:
            await interaction.followup.send(
                content=f"Deleted {count} message(s).",
                ephemeral=True,
            )
        except Exception:
            pass

        # Public confirmation in the channel that auto-deletes after 2 seconds
        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
                delete_after=2,
            )
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PurgeCog(bot))

