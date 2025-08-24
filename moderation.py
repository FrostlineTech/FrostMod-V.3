from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT, YELLOW, GREEN, RED
from ui import make_embed, PaginatorView

# Helpers

def parse_duration_to_timedelta(text: str) -> Optional[timedelta]:
    if not text:
        return None
    text = text.strip().lower()
    try:
        if text.endswith('s'):
            return timedelta(seconds=int(text[:-1]))
        if text.endswith('m'):
            return timedelta(minutes=int(text[:-1]))
        if text.endswith('h'):
            return timedelta(hours=int(text[:-1]))
        if text.endswith('d'):
            return timedelta(days=int(text[:-1]))
        # plain seconds
        return timedelta(seconds=int(text))
    except Exception:
        return None


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_modlog_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT modlog_channel_id FROM general_server WHERE guild_id=$1", guild.id)
            if not row:
                return None
            ch_id = row["modlog_channel_id"]
            if not ch_id:
                return None
            ch = guild.get_channel(ch_id)
            return ch if isinstance(ch, discord.TextChannel) else None

    async def log_case(self, guild: discord.Guild, target: discord.abc.User, moderator: discord.abc.User, action: str, reason: Optional[str]):
        pool = getattr(self.bot, "pool", None)
        case_id = None
        if pool:
            async with pool.acquire() as conn:
                rec = await conn.fetchrow(
                    "INSERT INTO mod_cases (guild_id, target_id, target_tag, moderator_id, action, reason) VALUES ($1,$2,$3,$4,$5,$6) RETURNING case_id",
                    guild.id, target.id, f"{target}", moderator.id, action, reason,
                )
                case_id = rec["case_id"] if rec else None
        # Send modlog if configured
        ch = await self.get_modlog_channel(guild)
        if ch:
            embed = discord.Embed(
                title=f"Case {case_id or '—'} • {action.title()}",
                description=(reason or "No reason provided."),
                color=YELLOW if action in {"warn"} else RED if action in {"ban", "mute", "lockdown"} else BRAND_COLOR,
            )
            embed.add_field(name="Target", value=f"{target} (`{target.id}`)", inline=True)
            embed.add_field(name="Moderator", value=f"{moderator} (`{moderator.id}`)", inline=True)
            embed.set_footer(text=FOOTER_TEXT)
            embed.timestamp = discord.utils.utcnow()
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

    # Config
    @app_commands.command(name="modlog_set", description="Set the modlog channel")
    @app_commands.describe(channel="Channel for moderation logs")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def modlog_set(self, interaction: discord.Interaction, channel: discord.TextChannel):
        pool = getattr(self.bot, "pool", None)
        if not pool or not interaction.guild:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO general_server (guild_id, guild_name, modlog_channel_id) VALUES ($1,$2,$3) "
                "ON CONFLICT (guild_id) DO UPDATE SET guild_name=EXCLUDED.guild_name, modlog_channel_id=EXCLUDED.modlog_channel_id",
                interaction.guild.id, interaction.guild.name, channel.id,
            )
        await interaction.response.send_message(f"Modlog channel set to {channel.mention}.", ephemeral=True)

    # Warn
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        if member == interaction.user:
            await interaction.response.send_message("You cannot warn yourself.", ephemeral=True)
            return
        await self.log_case(interaction.guild, member, interaction.user, "warn", reason)
        embed = make_embed(title="Member Warned", description=f"{member.mention} has been warned.", interaction=interaction, color=YELLOW)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            await member.send(f"You have been warned in {interaction.guild.name}. Reason: {reason or 'No reason provided.'}")
        except Exception:
            pass

    # Cases list
    @app_commands.command(name="cases", description="View recent moderation cases for a user")
    @app_commands.describe(member="Member to view cases for", limit="Number of recent cases")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def cases(self, interaction: discord.Interaction, member: Optional[discord.Member] = None, limit: int = 10):
        pool = getattr(self.bot, "pool", None)
        if not pool or not interaction.guild:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return
        target_id = (member or interaction.user).id
        limit = max(1, min(50, limit))
        rows = []
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT case_id, action, reason, created_at, moderator_id FROM mod_cases WHERE guild_id=$1 AND target_id=$2 ORDER BY case_id DESC LIMIT $3",
                interaction.guild.id, target_id, limit,
            )
        if not rows:
            await interaction.response.send_message("No cases found.", ephemeral=True)
            return
        pages: list[discord.Embed] = []
        for r in rows:
            e = make_embed(
                title=f"Case {r['case_id']} • {r['action'].title()}",
                description=r['reason'] or "No reason provided.",
                interaction=interaction,
            )
            e.add_field(name="When", value=discord.utils.format_dt(r['created_at'], style='R'), inline=True)
            e.add_field(name="Moderator", value=f"<@{r['moderator_id']}>", inline=True)
            pages.append(e)
        view = PaginatorView(pages)
        await interaction.response.send_message(embed=view.current, view=view, ephemeral=True)

    # Mute / Unmute using Discord timeouts
    @app_commands.command(name="mute", description="Timeout a member for a duration (e.g., 10m, 1h, 1d)")
    @app_commands.describe(member="Member to timeout", duration="Duration like 10m/1h/1d", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: Optional[str] = None):
        delta = parse_duration_to_timedelta(duration)
        if not delta or delta.total_seconds() < 1:
            await interaction.response.send_message("Invalid duration. Use formats like 30s, 10m, 1h, 1d.", ephemeral=True)
            return
        try:
            await member.timeout(delta, reason=reason or f"Muted by {interaction.user}")
            await self.log_case(interaction.guild, member, interaction.user, "mute", reason)
            await interaction.response.send_message(f"{member.mention} muted for {duration}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to timeout that member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to mute: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Remove a member's timeout")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        try:
            await member.timeout(None, reason=reason or f"Unmuted by {interaction.user}")
            await self.log_case(interaction.guild, member, interaction.user, "unmute", reason)
            await interaction.response.send_message(f"{member.mention} unmuted.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to modify that member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to unmute: {e}", ephemeral=True)

    # Ban / Unban
    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(member="Member to ban", reason="Reason")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        try:
            await interaction.guild.ban(member, reason=reason or f"Banned by {interaction.user}")
            await self.log_case(interaction.guild, member, interaction.user, "ban", reason)
            await interaction.response.send_message(f"{member} banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to ban that member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to ban: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="User ID to unban", reason="Reason")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, user_id: int, reason: Optional[str] = None):
        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user, reason=reason or f"Unbanned by {interaction.user}")
            await self.log_case(interaction.guild, user, interaction.user, "unban", reason)
            await interaction.response.send_message(f"{user} unbanned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to unban that user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to unban: {e}", ephemeral=True)

    # Slowmode / Lockdown
    @app_commands.command(name="slowmode", description="Set slowmode on a text channel")
    @app_commands.describe(channel="Channel (defaults to current)", seconds="Slowmode seconds (0 to disable)")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def slowmode(self, interaction: discord.Interaction, seconds: int, channel: Optional[discord.TextChannel] = None):
        ch = channel or (interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None)
        if ch is None:
            await interaction.response.send_message("Select a text channel.", ephemeral=True)
            return
        seconds = max(0, min(21600, seconds))
        try:
            await ch.edit(slowmode_delay=seconds)
            await interaction.response.send_message(f"Slowmode set to {seconds}s in {ch.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to edit that channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to set slowmode: {e}", ephemeral=True)

    @app_commands.command(name="lockdown", description="Toggle lockdown in a text channel (prevent @everyone from sending)")
    @app_commands.describe(channel="Channel (defaults to current)", enable="Enable lockdown (True) or disable (False)")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def lockdown(self, interaction: discord.Interaction, enable: bool, channel: Optional[discord.TextChannel] = None):
        ch = channel or (interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None)
        if ch is None:
            await interaction.response.send_message("Select a text channel.", ephemeral=True)
            return
        overwrites = ch.overwrites_for(interaction.guild.default_role)
        overwrites.send_messages = False if enable else None
        try:
            await ch.set_permissions(interaction.guild.default_role, overwrite=overwrites)
            await self.log_case(interaction.guild, interaction.user, interaction.user, "lockdown" if enable else "unlock", None)
            await interaction.response.send_message(f"{'Enabled' if enable else 'Disabled'} lockdown in {ch.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to edit channel permissions.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to update permissions: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
