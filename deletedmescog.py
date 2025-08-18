#this is the file for deleted message logging admin only 
#with /logs admins will recive an interactive ui to deisgnate the channel and toggle what gets logged we will add each ignored log as we add more loggable items
#the logs will be sent to the designated channel
#the logs will be sent in the format of 
#Username
#Message
#Time
#Channel

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class LogsConfigView(discord.ui.View):
    def __init__(self, *, guild: discord.Guild, pool, current_channel_id: int | None, log_msg_delete: bool,
                 log_nickname_change: bool = False, log_role_change: bool = False, log_avatar_change: bool = False,
                 log_message_edit: bool = False, log_member_join: bool = False, log_member_leave: bool = False):
        super().__init__(timeout=180)
        self.guild = guild
        self.pool = pool
        self.state_channel_id = current_channel_id
        self.state_log_msg_delete = log_msg_delete
        self.state_log_nickname_change = log_nickname_change
        self.state_log_role_change = log_role_change
        self.state_log_avatar_change = log_avatar_change
        self.state_log_message_edit = log_message_edit
        self.state_log_member_join = log_member_join
        self.state_log_member_leave = log_member_leave

        # Dynamic label for toggle button
        toggle_label = "Delete Log: ON" if log_msg_delete else "Delete Log: OFF"
        toggle_style = discord.ButtonStyle.success if log_msg_delete else discord.ButtonStyle.secondary

        # Add components
        self.add_item(_ChannelSelect(default_channel_id=current_channel_id))
        self.add_item(_ToggleDeleteButton(label=toggle_label, style=toggle_style))
        # Additional toggles
        self.add_item(_ToggleNicknameButton(label=("Nickname Log: ON" if log_nickname_change else "Nickname Log: OFF"),
                                            style=(discord.ButtonStyle.success if log_nickname_change else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleRoleButton(label=("Role Log: ON" if log_role_change else "Role Log: OFF"),
                                        style=(discord.ButtonStyle.success if log_role_change else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleAvatarButton(label=("Avatar Log: ON" if log_avatar_change else "Avatar Log: OFF"),
                                          style=(discord.ButtonStyle.success if log_avatar_change else discord.ButtonStyle.secondary)))
        # Message edit toggle
        self.add_item(_ToggleEditButton(label=("Edit Log: ON" if log_message_edit else "Edit Log: OFF"),
                                        style=(discord.ButtonStyle.success if log_message_edit else discord.ButtonStyle.secondary)))
        # Member join/leave toggles
        self.add_item(_ToggleJoinButton(label=("Join Log: ON" if log_member_join else "Join Log: OFF"),
                                        style=(discord.ButtonStyle.success if log_member_join else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleLeaveButton(label=("Leave Log: ON" if log_member_leave else "Leave Log: OFF"),
                                         style=(discord.ButtonStyle.success if log_member_leave else discord.ButtonStyle.secondary)))
        self.add_item(_SaveButton())

    async def save_to_db(self):
        if not self.pool:
            return False
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO general_server (guild_id, guild_name, logs_channel_id,
                                            log_message_delete, log_nickname_change, log_role_change, log_avatar_change,
                                            log_message_edit, log_member_join, log_member_leave)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (guild_id) DO UPDATE
                SET guild_name = EXCLUDED.guild_name,
                    logs_channel_id = EXCLUDED.logs_channel_id,
                    log_message_delete = EXCLUDED.log_message_delete,
                    log_nickname_change = EXCLUDED.log_nickname_change,
                    log_role_change = EXCLUDED.log_role_change,
                    log_avatar_change = EXCLUDED.log_avatar_change,
                    log_message_edit = EXCLUDED.log_message_edit,
                    log_member_join = EXCLUDED.log_member_join,
                    log_member_leave = EXCLUDED.log_member_leave
                """,
                self.guild.id,
                self.guild.name,
                self.state_channel_id,
                self.state_log_msg_delete,
                self.state_log_nickname_change,
                self.state_log_role_change,
                self.state_log_avatar_change,
                self.state_log_message_edit,
                self.state_log_member_join,
                self.state_log_member_leave,
            )
        return True


class _ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, default_channel_id: int | None):
        super().__init__(
            channel_types=[discord.ChannelType.text, discord.ChannelType.news, discord.ChannelType.forum],
            placeholder="Select a logs channel…",
            min_values=0,
            max_values=1,
        )
        self.default_channel_id = default_channel_id

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        picked = self.values[0] if self.values else None
        view.state_channel_id = picked.id if picked else None
        await interaction.response.defer()  # keep interaction alive without spamming messages


class _ToggleDeleteButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_msg_delete = not view.state_log_msg_delete
        # Update button appearance
        self.label = "Delete Log: ON" if view.state_log_msg_delete else "Delete Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_msg_delete else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleNicknameButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_nickname_change = not view.state_log_nickname_change
        self.label = "Nickname Log: ON" if view.state_log_nickname_change else "Nickname Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_nickname_change else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleRoleButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_role_change = not view.state_log_role_change
        self.label = "Role Log: ON" if view.state_log_role_change else "Role Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_role_change else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleAvatarButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_avatar_change = not view.state_log_avatar_change
        self.label = "Avatar Log: ON" if view.state_log_avatar_change else "Avatar Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_avatar_change else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleEditButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_message_edit = not view.state_log_message_edit
        self.label = "Edit Log: ON" if view.state_log_message_edit else "Edit Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_message_edit else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleJoinButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_member_join = not view.state_log_member_join
        self.label = "Join Log: ON" if view.state_log_member_join else "Join Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_member_join else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleLeaveButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_member_leave = not view.state_log_member_leave
        self.label = "Leave Log: ON" if view.state_log_member_leave else "Leave Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_member_leave else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _SaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Save", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        ok = await view.save_to_db()
        if ok:
            embed = discord.Embed(title="Logs Settings Saved", color=BRAND_COLOR)
            chan_mention = f"<#{view.state_channel_id}>" if view.state_channel_id else "Not set"
            embed.add_field(name="Logs Channel", value=chan_mention, inline=False)
            embed.add_field(name="Log Deleted Messages", value="Enabled" if view.state_log_msg_delete else "Disabled", inline=False)
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message("Database not configured.", ephemeral=True)


class DeletedMessageLogger(commands.Cog):
    """Cog for logging deleted messages and configuring logging via /logs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_deleter(self, message: discord.Message) -> discord.Member | None:
        """Best-effort: find who deleted the message via audit logs.
        Only works for moderator deletions; user self-deletes generally don't appear in audit logs.
        """
        guild = message.guild
        if guild is None:
            return None
        try:
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete):
                # entry.target is the user whose message was deleted; extra may include channel_id and count
                if getattr(entry.target, "id", None) != message.author.id:
                    continue
                extra = getattr(entry, "extra", None)
                if extra is not None and getattr(extra, "channel", None):
                    # Match channel when available
                    if getattr(extra.channel, "id", None) != message.channel.id:
                        continue
                user = entry.user
                return user if isinstance(user, discord.Member) else guild.get_member(user.id)
        except discord.Forbidden:
            # Missing permissions to view audit logs
            return None
        except Exception:
            return None
        
        return None

    async def _resolve_member_remove(self, guild: discord.Guild, member: discord.Member):
        """Try to determine if a removal was a kick or ban and by whom using audit logs.
        Returns a tuple (action: str | None, actor: discord.Member | None).
        """
        try:
            now = discord.utils.utcnow()
            async for entry in guild.audit_logs(limit=10):
                # Only consider recent entries to avoid mismatches
                if entry.created_at and (now - entry.created_at).total_seconds() > 60:
                    continue
                if getattr(entry.target, "id", None) != member.id:
                    continue
                if entry.action == discord.AuditLogAction.kick:
                    actor = entry.user if isinstance(entry.user, discord.Member) else guild.get_member(entry.user.id)
                    return ("Kick", actor)
                if entry.action == discord.AuditLogAction.ban:
                    actor = entry.user if isinstance(entry.user, discord.Member) else guild.get_member(entry.user.id)
                    return ("Ban", actor)
        except discord.Forbidden:
            return (None, None)
        except Exception:
            return (None, None)
        return (None, None)

    # Guild-only, admin-level UI
    @app_commands.command(name="logs", description="Configure server logs: channel and toggles")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def logs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("This command must be used in a server.", ephemeral=True)
            return

        pool = getattr(self.bot, "pool", None)
        current_channel_id = None
        log_msg_delete = False
        log_nickname = False
        log_role = False
        log_avatar = False
        log_edit = False
        log_join = False
        log_leave = False

        # Load current settings if available
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT logs_channel_id, log_message_delete, log_nickname_change, log_role_change, log_avatar_change, log_message_edit, log_member_join, log_member_leave FROM general_server WHERE guild_id = $1",
                    guild.id,
                )
                if row:
                    current_channel_id = row["logs_channel_id"]
                    log_msg_delete = row["log_message_delete"]
                    log_nickname = row["log_nickname_change"]
                    log_role = row["log_role_change"]
                    log_avatar = row["log_avatar_change"]
                    log_edit = row["log_message_edit"]
                    log_join = row["log_member_join"]
                    log_leave = row["log_member_leave"]

        view = LogsConfigView(
            guild=guild,
            pool=pool,
            current_channel_id=current_channel_id,
            log_msg_delete=log_msg_delete,
            log_nickname_change=log_nickname,
            log_role_change=log_role,
            log_avatar_change=log_avatar,
            log_message_edit=log_edit,
            log_member_join=log_join,
            log_member_leave=log_leave,
        )

        embed = discord.Embed(title="Logs Configuration", color=BRAND_COLOR)
        embed.description = (
            "Use the selector to choose a logs channel and the button to toggle deleted message logging."
        )
        chan_mention = f"<#{current_channel_id}>" if current_channel_id else "Not set"
        embed.add_field(name="Current Logs Channel", value=chan_mention, inline=False)
        embed.add_field(name="Log Deleted Messages", value="Enabled" if log_msg_delete else "Disabled", inline=False)
        embed.add_field(name="Log Edits", value="Enabled" if log_edit else "Disabled", inline=True)
        embed.add_field(name="Log Nickname Changes", value="Enabled" if log_nickname else "Disabled", inline=True)
        embed.add_field(name="Log Role Changes", value="Enabled" if log_role else "Disabled", inline=True)
        embed.add_field(name="Log Avatar Changes", value="Enabled" if log_avatar else "Disabled", inline=True)
        embed.add_field(name="Log Joins", value="Enabled" if log_join else "Disabled", inline=True)
        embed.add_field(name="Log Leaves", value="Enabled" if log_leave else "Disabled", inline=True)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # Ignore DMs or system messages
        if message.guild is None or message.author.bot:
            return

        pool = getattr(self.bot, "pool", None)
        if not pool:
            return

        # Fetch settings
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_message_delete FROM general_server WHERE guild_id = $1",
                message.guild.id,
            )
        if not row or not row["log_message_delete"]:
            return

        logs_channel_id = row["logs_channel_id"]
        if not logs_channel_id:
            return

        channel = message.guild.get_channel(logs_channel_id)
        if channel is None:
            # Attempt fetch in case it's a thread or not cached
            try:
                channel = await self.bot.fetch_channel(logs_channel_id)
            except Exception:
                return

        # Build embed
        embed = discord.Embed(title="Message Deleted", color=BRAND_COLOR)
        embed.add_field(name="User", value=f"{message.author} (ID: {message.author.id})", inline=False)
        content = message.content or "<no text content>"
        # Limit extremely long content to avoid exceeding limits
        if len(content) > 1500:
            content = content[:1500] + "…"
        embed.add_field(name="Message", value=content, inline=False)
        ts = discord.utils.format_dt(message.created_at, style="F") if message.created_at else "Unknown time"
        embed.add_field(name="Time", value=ts, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        if message.attachments:
            files_text = "\n".join(a.url for a in message.attachments[:5])
            embed.add_field(name="Attachments", value=files_text, inline=False)
        # Attempt to include moderator/admin if applicable
        deleter = await self._resolve_deleter(message)
        if deleter is not None:
            embed.add_field(name="Deleted By", value=f"{deleter.mention} ({deleter})", inline=False)
        embed.set_footer(text=FOOTER_TEXT)

        try:
            await channel.send(embed=embed)
        except Exception:
            # Swallow send errors silently to avoid cascading failures
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_message_edit FROM general_server WHERE guild_id = $1",
                before.guild.id,
            )
        if not row or not row["log_message_edit"] or not row["logs_channel_id"]:
            return
        channel = before.guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if channel is None:
            return
        embed = discord.Embed(title="Message Edited", color=BRAND_COLOR)
        embed.add_field(name="User", value=f"{before.author} (ID: {before.author.id})", inline=False)
        old = before.content or "<no text content>"
        new = after.content or "<no text content>"
        if len(old) > 1000:
            old = old[:1000] + "…"
        if len(new) > 1000:
            new = new[:1000] + "…"
        embed.add_field(name="Before", value=old, inline=False)
        embed.add_field(name="After", value=new, inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        embed.add_field(name="Edited By", value=f"{before.author.mention} ({before.author})", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_member_join FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["log_member_join"] or not row["logs_channel_id"]:
            return
        channel = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if channel is None:
            return
        embed = discord.Embed(title="Member Joined", color=BRAND_COLOR)
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=False)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style="F"), inline=True)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_member_leave FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["log_member_leave"] or not row["logs_channel_id"]:
            return
        channel = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if channel is None:
            return
        action, actor = await self._resolve_member_remove(guild, member)
        title = "Member Left"
        if action == "Kick":
            title = "Member Kicked"
        elif action == "Ban":
            title = "Member Banned"
        embed = discord.Embed(title=title, color=BRAND_COLOR)
        embed.add_field(name="User", value=f"{member} (ID: {member.id})", inline=False)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(DeletedMessageLogger(bot))
