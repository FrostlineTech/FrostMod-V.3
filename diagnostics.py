from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, GREEN, YELLOW, RED, FOOTER_TEXT
from ui import make_embed


def perm_emoji(ok: bool) -> str:
    return "✅" if ok else "❌"


class Diagnostics(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    async def _check_channel_perms(self, guild: discord.Guild, channel_id: int | None) -> tuple[str, list[tuple[str, bool]]]:
        if not channel_id:
            return ("Not configured", [])
        ch = guild.get_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return ("Invalid channel", [])
        me = guild.me
        perms = ch.permissions_for(me)
        checks = [
            ("View Channel", perms.view_channel),
            ("Send Messages", perms.send_messages),
            ("Embed Links", perms.embed_links),
            ("Attach Files", perms.attach_files),
            ("Add Reactions", perms.add_reactions),
            ("Manage Messages (for moderation)", perms.manage_messages),
        ]
        return (ch.mention, checks)

    @app_commands.command(name="diagnose", description="Check bot configuration and permissions for this server")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def diagnose(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        pool = getattr(self.bot, "pool", None)
        welcome_channel_id = leave_channel_id = logs_channel_id = None
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT welcome_channel_id, leave_channel_id, logs_channel_id FROM general_server WHERE guild_id=$1",
                        interaction.guild.id,
                    )
                    if row:
                        welcome_channel_id = row["welcome_channel_id"]
                        leave_channel_id = row["leave_channel_id"]
                        logs_channel_id = row["logs_channel_id"]
            except Exception:
                pass

        sections = []
        for label, cid in (
            ("Welcome", welcome_channel_id),
            ("Leave", leave_channel_id),
            ("Logs", logs_channel_id),
        ):
            where, checks = await self._check_channel_perms(interaction.guild, cid)
            lines = [f"{perm_emoji(ok)} {name}" for name, ok in checks]
            sections.append((label, where, lines))

        embed = make_embed(
            title=f"Diagnostics — {interaction.guild.name}",
            description="Permission checks for configured channels.",
            interaction=interaction,
        )
        for label, where, lines in sections:
            value = f"{where}\n" + ("\n".join(lines) if lines else "")
            embed.add_field(name=label, value=value or "Not configured", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Diagnostics(bot))
