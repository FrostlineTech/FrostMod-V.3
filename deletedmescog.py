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
                 log_message_edit: bool = False, log_member_join: bool = False, log_member_leave: bool = False,
                 log_voice_join: bool = False, log_voice_leave: bool = False,
                 log_bulk_delete: bool = False,
                 log_channel_create: bool = False, log_channel_delete: bool = False, log_channel_update: bool = False,
                 log_thread_create: bool = False, log_thread_delete: bool = False, log_thread_update: bool = False):
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
        self.state_log_voice_join = log_voice_join
        self.state_log_voice_leave = log_voice_leave
        # Expanded toggles
        self.state_log_bulk_delete = log_bulk_delete
        self.state_log_channel_create = log_channel_create
        self.state_log_channel_delete = log_channel_delete
        self.state_log_channel_update = log_channel_update
        self.state_log_thread_create = log_thread_create
        self.state_log_thread_delete = log_thread_delete
        self.state_log_thread_update = log_thread_update

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
        # Voice join/leave toggles
        self.add_item(_ToggleVoiceJoinButton(label=("Voice Join Log: ON" if log_voice_join else "Voice Join Log: OFF"),
                                             style=(discord.ButtonStyle.success if log_voice_join else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleVoiceLeaveButton(label=("Voice Leave Log: ON" if log_voice_leave else "Voice Leave Log: OFF"),
                                              style=(discord.ButtonStyle.success if log_voice_leave else discord.ButtonStyle.secondary)))
        # Expanded: bulk delete and channel/thread events
        self.add_item(_ToggleBulkDeleteButton(label=("Bulk Delete Log: ON" if log_bulk_delete else "Bulk Delete Log: OFF"),
                                              style=(discord.ButtonStyle.success if log_bulk_delete else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleChanCreateButton(label=("Channel Create Log: ON" if log_channel_create else "Channel Create Log: OFF"),
                                              style=(discord.ButtonStyle.success if log_channel_create else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleChanDeleteButton(label=("Channel Delete Log: ON" if log_channel_delete else "Channel Delete Log: OFF"),
                                              style=(discord.ButtonStyle.success if log_channel_delete else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleChanUpdateButton(label=("Channel Update Log: ON" if log_channel_update else "Channel Update Log: OFF"),
                                              style=(discord.ButtonStyle.success if log_channel_update else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleThreadCreateButton(label=("Thread Create Log: ON" if log_thread_create else "Thread Create Log: OFF"),
                                                style=(discord.ButtonStyle.success if log_thread_create else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleThreadDeleteButton(label=("Thread Delete Log: ON" if log_thread_delete else "Thread Delete Log: OFF"),
                                                style=(discord.ButtonStyle.success if log_thread_delete else discord.ButtonStyle.secondary)))
        self.add_item(_ToggleThreadUpdateButton(label=("Thread Update Log: ON" if log_thread_update else "Thread Update Log: OFF"),
                                                style=(discord.ButtonStyle.success if log_thread_update else discord.ButtonStyle.secondary)))
        self.add_item(_SaveButton())

    async def save_to_db(self):
        if not self.pool:
            return False
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO general_server (guild_id, guild_name, logs_channel_id,
                                            log_message_delete, log_nickname_change, log_role_change, log_avatar_change,
                                            log_message_edit, log_member_join, log_member_leave, log_voice_join, log_voice_leave,
                                            log_bulk_delete, log_channel_create, log_channel_delete, log_channel_update,
                                            log_thread_create, log_thread_delete, log_thread_update)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (guild_id) DO UPDATE
                SET guild_name = EXCLUDED.guild_name,
                    logs_channel_id = EXCLUDED.logs_channel_id,
                    log_message_delete = EXCLUDED.log_message_delete,
                    log_nickname_change = EXCLUDED.log_nickname_change,
                    log_role_change = EXCLUDED.log_role_change,
                    log_avatar_change = EXCLUDED.log_avatar_change,
                    log_message_edit = EXCLUDED.log_message_edit,
                    log_member_join = EXCLUDED.log_member_join,
                    log_member_leave = EXCLUDED.log_member_leave,
                    log_voice_join = EXCLUDED.log_voice_join,
                    log_voice_leave = EXCLUDED.log_voice_leave,
                    log_bulk_delete = EXCLUDED.log_bulk_delete,
                    log_channel_create = EXCLUDED.log_channel_create,
                    log_channel_delete = EXCLUDED.log_channel_delete,
                    log_channel_update = EXCLUDED.log_channel_update,
                    log_thread_create = EXCLUDED.log_thread_create,
                    log_thread_delete = EXCLUDED.log_thread_delete,
                    log_thread_update = EXCLUDED.log_thread_update
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
                self.state_log_voice_join,
                self.state_log_voice_leave,
                self.state_log_bulk_delete,
                self.state_log_channel_create,
                self.state_log_channel_delete,
                self.state_log_channel_update,
                self.state_log_thread_create,
                self.state_log_thread_delete,
                self.state_log_thread_update,
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


class _ToggleBulkDeleteButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_bulk_delete = not view.state_log_bulk_delete
        self.label = "Bulk Delete Log: ON" if view.state_log_bulk_delete else "Bulk Delete Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_bulk_delete else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleChanCreateButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_channel_create = not view.state_log_channel_create
        self.label = "Channel Create Log: ON" if view.state_log_channel_create else "Channel Create Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_channel_create else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleChanDeleteButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_channel_delete = not view.state_log_channel_delete
        self.label = "Channel Delete Log: ON" if view.state_log_channel_delete else "Channel Delete Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_channel_delete else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleChanUpdateButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_channel_update = not view.state_log_channel_update
        self.label = "Channel Update Log: ON" if view.state_log_channel_update else "Channel Update Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_channel_update else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleThreadCreateButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=3)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_thread_create = not view.state_log_thread_create
        self.label = "Thread Create Log: ON" if view.state_log_thread_create else "Thread Create Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_thread_create else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleThreadDeleteButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_thread_delete = not view.state_log_thread_delete
        self.label = "Thread Delete Log: ON" if view.state_log_thread_delete else "Thread Delete Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_thread_delete else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleThreadUpdateButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_thread_update = not view.state_log_thread_update
        self.label = "Thread Update Log: ON" if view.state_log_thread_update else "Thread Update Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_thread_update else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleVoiceJoinButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_voice_join = not view.state_log_voice_join
        self.label = "Voice Join Log: ON" if view.state_log_voice_join else "Voice Join Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_voice_join else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=view)


class _ToggleVoiceLeaveButton(discord.ui.Button):
    def __init__(self, *, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: LogsConfigView = self.view  # type: ignore
        view.state_log_voice_leave = not view.state_log_voice_leave
        self.label = "Voice Leave Log: ON" if view.state_log_voice_leave else "Voice Leave Log: OFF"
        self.style = discord.ButtonStyle.success if view.state_log_voice_leave else discord.ButtonStyle.secondary
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

    async def _find_audit_actor(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        target_id: int | None = None,
        channel_id: int | None = None,
        limit: int = 5,
        seconds: int = 120,
    ) -> tuple[discord.Member | None, str | None]:
        """Try to resolve who performed an action and an optional reason from audit logs.
        Filters to recent entries and optionally matches target_id or channel in extras.
        Returns (member_or_none, reason_or_none).
        """
        try:
            now = discord.utils.utcnow()
            async for entry in guild.audit_logs(limit=limit, action=action):
                if entry.created_at and (now - entry.created_at).total_seconds() > seconds:
                    continue
                if target_id is not None and getattr(entry.target, "id", None) != target_id:
                    continue
                extra = getattr(entry, "extra", None)
                if channel_id is not None and hasattr(extra, "channel"):
                    if getattr(extra.channel, "id", None) != channel_id:
                        continue
                user = entry.user
                member = user if isinstance(user, discord.Member) else guild.get_member(getattr(user, "id", 0))
                reason = entry.reason if isinstance(entry.reason, str) else None
                return (member, reason)
        except discord.Forbidden:
            return (None, None)
        except Exception:
            return (None, None)
        return (None, None)

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
        log_vjoin = False
        log_vleave = False
        log_bulk = False
        log_chan_create = False
        log_chan_delete = False
        log_chan_update = False
        log_th_create = False
        log_th_delete = False
        log_th_update = False

        # Load current settings if available
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT logs_channel_id, log_message_delete, log_nickname_change, log_role_change, log_avatar_change, log_message_edit, log_member_join, log_member_leave, log_voice_join, log_voice_leave, log_bulk_delete, log_channel_create, log_channel_delete, log_channel_update, log_thread_create, log_thread_delete, log_thread_update FROM general_server WHERE guild_id = $1",
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
                    log_vjoin = row["log_voice_join"]
                    log_vleave = row["log_voice_leave"]
                    log_bulk = row["log_bulk_delete"]
                    log_chan_create = row["log_channel_create"]
                    log_chan_delete = row["log_channel_delete"]
                    log_chan_update = row["log_channel_update"]
                    log_th_create = row["log_thread_create"]
                    log_th_delete = row["log_thread_delete"]
                    log_th_update = row["log_thread_update"]

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
            log_voice_join=log_vjoin,
            log_voice_leave=log_vleave,
            log_bulk_delete=log_bulk,
            log_channel_create=log_chan_create,
            log_channel_delete=log_chan_delete,
            log_channel_update=log_chan_update,
            log_thread_create=log_th_create,
            log_thread_delete=log_th_delete,
            log_thread_update=log_th_update,
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
        embed.add_field(name="Log Voice Joins", value="Enabled" if log_vjoin else "Disabled", inline=True)
        embed.add_field(name="Log Voice Leaves", value="Enabled" if log_vleave else "Disabled", inline=True)
        embed.add_field(name="Log Bulk Deletes", value="Enabled" if log_bulk else "Disabled", inline=True)
        embed.add_field(name="Log Channel Create", value="Enabled" if log_chan_create else "Disabled", inline=True)
        embed.add_field(name="Log Channel Delete", value="Enabled" if log_chan_delete else "Disabled", inline=True)
        embed.add_field(name="Log Channel Update", value="Enabled" if log_chan_update else "Disabled", inline=True)
        embed.add_field(name="Log Thread Create", value="Enabled" if log_th_create else "Disabled", inline=True)
        embed.add_field(name="Log Thread Delete", value="Enabled" if log_th_delete else "Disabled", inline=True)
        embed.add_field(name="Log Thread Update", value="Enabled" if log_th_update else "Disabled", inline=True)
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
        embed.add_field(name="Channel", value=f"{message.channel.mention} (ID: {message.channel.id})", inline=True)
        embed.add_field(name="Message ID", value=str(message.id), inline=True)
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
        embed.add_field(name="Channel", value=f"{before.channel.mention} (ID: {before.channel.id})", inline=True)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        embed.add_field(name="Message ID", value=str(before.id), inline=True)
        try:
            embed.add_field(name="Jump", value=f"[Go to message]({after.jump_url})", inline=False)
        except Exception:
            pass
        embed.add_field(name="Edited By", value=f"{before.author.mention} ({before.author})", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
        if guild is None:
            return
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_bulk_delete FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_bulk_delete"]:
            return
        channel = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if channel is None:
            return
        # Note: payload.channel_id is the channel messages were deleted from
        src = guild.get_channel(payload.channel_id)
        embed = discord.Embed(title="Bulk Messages Deleted", color=BRAND_COLOR)
        embed.add_field(name="Channel", value=(src.mention if src else f"ID: {payload.channel_id}"), inline=True)
        embed.add_field(name="Count", value=str(len(payload.message_ids)), inline=True)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.message_bulk_delete, channel_id=payload.channel_id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_channel_create FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_channel_create"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        embed = discord.Embed(title="Channel Created", color=BRAND_COLOR)
        embed.add_field(name="Name", value=f"{getattr(channel, 'mention', '#'+channel.name)}", inline=True)
        embed.add_field(name="Type", value=channel.type.name if hasattr(channel, 'type') else "Unknown", inline=True)
        embed.add_field(name="ID", value=str(channel.id), inline=True)
        try:
            cat = getattr(channel, "category", None)
            if cat:
                embed.add_field(name="Category", value=f"{cat.name} (ID: {cat.id})", inline=True)
            pos = getattr(channel, "position", None)
            if isinstance(pos, int):
                embed.add_field(name="Position", value=str(pos), inline=True)
        except Exception:
            pass
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.channel_create, target_id=channel.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_channel_delete FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_channel_delete"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        embed = discord.Embed(title="Channel Deleted", color=BRAND_COLOR)
        try:
            embed.add_field(name="Name", value=f"#{getattr(channel, 'name', 'unknown')}", inline=True)
        except Exception:
            pass
        embed.add_field(name="ID", value=str(channel.id), inline=True)
        embed.add_field(name="Type", value=channel.type.name if hasattr(channel, 'type') else "Unknown", inline=True)
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.channel_delete, target_id=channel.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild = after.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_channel_update FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_channel_update"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        changes = []
        try:
            if getattr(before, 'name', None) != getattr(after, 'name', None):
                changes.append(f"Name: {getattr(before, 'name', None)} ➜ {getattr(after, 'name', None)}")
            if getattr(before, 'topic', None) != getattr(after, 'topic', None):
                changes.append("Topic updated")
            if getattr(before, 'nsfw', None) != getattr(after, 'nsfw', None):
                changes.append(f"NSFW: {getattr(before, 'nsfw', None)} ➜ {getattr(after, 'nsfw', None)}")
            if getattr(before, 'slowmode_delay', None) != getattr(after, 'slowmode_delay', None):
                changes.append(f"Slowmode: {getattr(before, 'slowmode_delay', None)} ➜ {getattr(after, 'slowmode_delay', None)}")
            if getattr(before, 'position', None) != getattr(after, 'position', None):
                changes.append(f"Position: {getattr(before, 'position', None)} ➜ {getattr(after, 'position', None)}")
        except Exception:
            pass
        desc = "\n".join(changes) if changes else "(No diff captured)"
        embed = discord.Embed(title="Channel Updated", description=desc, color=BRAND_COLOR)
        embed.add_field(name="Channel", value=f"{getattr(after, 'mention', '#'+after.name)}", inline=False)
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.channel_update, target_id=after.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        guild = thread.guild
        pool = getattr(self.bot, "pool", None)
        if not pool or guild is None:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_thread_create FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_thread_create"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        embed = discord.Embed(title="Thread Created", color=BRAND_COLOR)
        embed.add_field(name="Name", value=thread.mention, inline=True)
        embed.add_field(name="Parent", value=thread.parent.mention if thread.parent else "None", inline=True)
        embed.add_field(name="ID", value=str(thread.id), inline=True)
        try:
            embed.add_field(name="Auto-Archive", value=f"{thread.auto_archive_duration} min", inline=True)
            if thread.slowmode_delay:
                embed.add_field(name="Slowmode", value=f"{thread.slowmode_delay}s", inline=True)
        except Exception:
            pass
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.thread_create, target_id=thread.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        guild = thread.guild
        pool = getattr(self.bot, "pool", None)
        if not pool or guild is None:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_thread_delete FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_thread_delete"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        embed = discord.Embed(title="Thread Deleted", color=BRAND_COLOR)
        try:
            embed.add_field(name="Name", value=f"{getattr(thread, 'name', 'Unknown')}", inline=True)
        except Exception:
            pass
        embed.add_field(name="ID", value=str(thread.id), inline=True)
        embed.add_field(name="Parent", value=thread.parent.mention if thread.parent else "None", inline=True)
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.thread_delete, target_id=thread.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        guild = after.guild
        pool = getattr(self.bot, "pool", None)
        if not pool or guild is None:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_thread_update FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"] or not row["log_thread_update"]:
            return
        logs_ch = guild.get_channel(row["logs_channel_id"]) or await self.bot.fetch_channel(row["logs_channel_id"])  # type: ignore
        if logs_ch is None:
            return
        changes = []
        if before.name != after.name:
            changes.append(f"Name: {before.name} ➜ {after.name}")
        if before.archived != after.archived:
            changes.append(f"Archived: {before.archived} ➜ {after.archived}")
        if before.locked != after.locked:
            changes.append(f"Locked: {before.locked} ➜ {after.locked}")
        if before.auto_archive_duration != after.auto_archive_duration:
            changes.append(f"Auto-Archive: {before.auto_archive_duration} ➜ {after.auto_archive_duration}")
        if before.slowmode_delay != after.slowmode_delay:
            changes.append(f"Slowmode: {before.slowmode_delay}s ➜ {after.slowmode_delay}s")
        desc = "\n".join(changes) if changes else "(No diff captured)"
        embed = discord.Embed(title="Thread Updated", description=desc, color=BRAND_COLOR)
        embed.add_field(name="Thread", value=after.mention, inline=False)
        actor, reason = await self._find_audit_actor(guild, discord.AuditLogAction.thread_update, target_id=after.id)
        if actor is not None:
            embed.add_field(name="By", value=f"{actor.mention} ({actor})", inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await logs_ch.send(embed=embed)
        except Exception:
            pass


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_voice_join, log_voice_leave FROM general_server WHERE guild_id = $1",
                guild.id,
            )
        if not row or not row["logs_channel_id"]:
            return
        logs_channel_id = row["logs_channel_id"]
        channel = guild.get_channel(logs_channel_id) or await self.bot.fetch_channel(logs_channel_id)  # type: ignore
        if channel is None:
            return

        joined = before.channel is None and after.channel is not None
        left = before.channel is not None and after.channel is None
        moved = before.channel is not None and after.channel is not None and before.channel.id != after.channel.id

        try:
            if (joined or moved) and row["log_voice_join"]:
                dest = after.channel
                embed = discord.Embed(title="Voice Channel Joined", color=BRAND_COLOR)
                embed.add_field(name="User", value=f"{member} (ID: {member.id})", inline=False)
                if moved and before.channel:
                    embed.add_field(name="From", value=f"{before.channel.mention}", inline=True)
                embed.add_field(name="To", value=f"{dest.mention if dest else 'Unknown'}", inline=True)
                embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=False)
                embed.set_footer(text=FOOTER_TEXT)
                await channel.send(embed=embed)

            if (left or moved) and row["log_voice_leave"]:
                src = before.channel
                embed = discord.Embed(title="Voice Channel Left", color=BRAND_COLOR)
                embed.add_field(name="User", value=f"{member} (ID: {member.id})", inline=False)
                embed.add_field(name="From", value=f"{src.mention if src else 'Unknown'}", inline=True)
                if moved and after.channel:
                    embed.add_field(name="To", value=f"{after.channel.mention}", inline=True)
                embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=False)
                embed.set_footer(text=FOOTER_TEXT)
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
        embed.add_field(name="User ID", value=str(member.id), inline=True)
        embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, style="F"), inline=True)
        try:
            age_days = (discord.utils.utcnow() - member.created_at).days
            embed.add_field(name="Account Age", value=f"{age_days} days", inline=True)
        except Exception:
            pass
        try:
            embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        except Exception:
            pass
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
        try:
            if member.joined_at:
                embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style="F"), inline=True)
        except Exception:
            pass
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
