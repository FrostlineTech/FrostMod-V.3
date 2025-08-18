from __future__ import annotations

import discord
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class UserChangeLogger(commands.Cog):
    """Logs user updates (nickname, roles, avatar) to the configured logs channel based on toggles."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_settings(self, guild_id: int):
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT logs_channel_id, log_nickname_change, log_role_change, log_avatar_change
                FROM general_server WHERE guild_id = $1
                """,
                guild_id,
            )
        return row

    async def _get_logs_channel(self, guild: discord.Guild, channel_id: int | None):
        if not channel_id:
            return None
        ch = guild.get_channel(channel_id)
        if ch is None:
            try:
                ch = await self.bot.fetch_channel(channel_id)
            except Exception:
                return None
        return ch

    async def _resolve_actor(self, guild: discord.Guild, member: discord.Member, actions: list[discord.AuditLogAction]):
        """Try to find the moderator/admin who made the change using audit logs.
        Returns a Member or None. Requires View Audit Log permission.
        """
        try:
            async for entry in guild.audit_logs(limit=10):
                if entry.action not in actions:
                    continue
                if getattr(entry.target, "id", None) != member.id:
                    continue
                # Found a matching action targeting this member
                user = entry.user
                return user if isinstance(user, discord.Member) else guild.get_member(user.id)
        except discord.Forbidden:
            return None
        except Exception:
            return None
        return None

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild is None:
            return

        settings = await self._get_settings(before.guild.id)
        if not settings:
            return

        logs_channel = await self._get_logs_channel(before.guild, settings["logs_channel_id"])
        if logs_channel is None:
            return

        # Track changes
        changed = False

        # Nickname change
        if settings["log_nickname_change"]:
            if before.nick != after.nick:
                embed = discord.Embed(title="Nickname Changed", color=BRAND_COLOR)
                embed.add_field(name="User", value=f"{after} (ID: {after.id})", inline=False)
                embed.add_field(name="Old Nickname", value=before.nick or "None", inline=True)
                embed.add_field(name="New Nickname", value=after.nick or "None", inline=True)
                embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), "F"), inline=False)
                actor = await self._resolve_actor(before.guild, after, [discord.AuditLogAction.member_update])
                if actor is not None:
                    embed.add_field(name="Changed By", value=f"{actor.mention} ({actor})", inline=False)
                embed.set_footer(text=FOOTER_TEXT)
                try:
                    await logs_channel.send(embed=embed)
                except Exception:
                    pass
                changed = True

        # Role change
        if settings["log_role_change"]:
            before_roles = [r for r in before.roles if r.name != "@everyone"]
            after_roles = [r for r in after.roles if r.name != "@everyone"]
            if set(before_roles) != set(after_roles):
                added = [r.mention for r in after_roles if r not in before_roles]
                removed = [r.mention for r in before_roles if r not in after_roles]
                embed = discord.Embed(title="Roles Updated", color=BRAND_COLOR)
                embed.add_field(name="User", value=f"{after} (ID: {after.id})", inline=False)
                if added:
                    embed.add_field(name="Added", value=", ".join(added), inline=False)
                if removed:
                    embed.add_field(name="Removed", value=", ".join(removed), inline=False)
                if not added and not removed:
                    embed.add_field(name="Change", value="(No net change detected)", inline=False)
                embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), "F"), inline=False)
                actor = await self._resolve_actor(before.guild, after, [discord.AuditLogAction.member_role_update])
                if actor is not None:
                    embed.add_field(name="Changed By", value=f"{actor.mention} ({actor})", inline=False)
                embed.set_footer(text=FOOTER_TEXT)
                try:
                    await logs_channel.send(embed=embed)
                except Exception:
                    pass
                changed = True

        # Avatar change (global or server avatar)
        if settings["log_avatar_change"]:
            # Compare display avatar asset key or URL
            before_url = str(before.display_avatar.url) if before.display_avatar else None
            after_url = str(after.display_avatar.url) if after.display_avatar else None
            if before_url != after_url:
                embed = discord.Embed(title="Avatar Changed", color=BRAND_COLOR)
                embed.add_field(name="User", value=f"{after} (ID: {after.id})", inline=False)
                if before_url:
                    embed.set_thumbnail(url=before_url)
                if after_url:
                    embed.set_image(url=after_url)
                embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), "F"), inline=False)
                actor = await self._resolve_actor(before.guild, after, [discord.AuditLogAction.member_update])
                if actor is not None:
                    embed.add_field(name="Changed By", value=f"{actor.mention} ({actor})", inline=False)
                embed.set_footer(text=FOOTER_TEXT)
                try:
                    await logs_channel.send(embed=embed)
                except Exception:
                    pass
                changed = True

        if not changed:
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(UserChangeLogger(bot))

