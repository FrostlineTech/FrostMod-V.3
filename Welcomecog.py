#welcome cog ensure this cog is registered in the molls.py file
#ensure all embeds say powered by FSLLC / FrostlineSolutions.com at the bottom of the embed in the footer
#ensure all embeds are color purple (0x8e00ff)

from __future__ import annotations

import logging
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

PURPLE = 0x8E00FF
FOOTER_TEXT = "Powered by FSLLC / FrostlineSolutions.com"


class WelcomeCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    # Config commands
    group = app_commands.Group(name="welcome", description="Configure welcome settings")

    @group.command(name="channel", description="Set the channel for welcome messages")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not getattr(self.bot, "pool", None):
            await interaction.response.send_message("Database not configured.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            self.log.info(f"[DB] Upserting welcome_channel_id guild={interaction.guild.id} channel={channel.id}")
            await conn.execute(
                """
                INSERT INTO general_server (guild_id, guild_name, welcome_channel_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO UPDATE SET guild_name = EXCLUDED.guild_name, welcome_channel_id = EXCLUDED.welcome_channel_id
                """,
                interaction.guild.id,
                interaction.guild.name,
                channel.id,
            )
            self.log.info(f"[DB] Upserted welcome_channel_id for guild={interaction.guild.id}")
        await interaction.followup.send(f"Welcome channel set to {channel.mention}.", ephemeral=True)

    @group.command(name="message", description="Set the welcome message template")
    @app_commands.describe(message="Template using {user}, {guild}, {membercount}")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def set_message(self, interaction: discord.Interaction, message: str):
        if not getattr(self.bot, "pool", None):
            await interaction.response.send_message("Database not configured.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            self.log.info(f"[DB] Upserting welcome_message guild={interaction.guild.id}")
            await conn.execute(
                """
                INSERT INTO general_server (guild_id, guild_name, welcome_message)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO UPDATE SET guild_name = EXCLUDED.guild_name, welcome_message = EXCLUDED.welcome_message
                """,
                interaction.guild.id,
                interaction.guild.name,
                message,
            )
            self.log.info(f"[DB] Upserted welcome_message for guild={interaction.guild.id}")
        await interaction.followup.send("Welcome message updated.", ephemeral=True)

    @group.command(name="setup", description="Interactive setup for welcome channel and message")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def setup_welcome(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        pool = getattr(self.bot, "pool", None)
        current_channel_id = None
        current_message = None
        if pool:
            async with pool.acquire() as conn:
                self.log.info(f"[DB] Fetching welcome config for setup guild={interaction.guild.id}")
                row = await conn.fetchrow(
                    "SELECT welcome_channel_id, welcome_message FROM general_server WHERE guild_id=$1",
                    interaction.guild.id,
                )
                if row:
                    current_channel_id = row["welcome_channel_id"]
                    current_message = row["welcome_message"]

        class TemplateModal(discord.ui.Modal, title="Edit Welcome Template"):
            def __init__(self, default: str | None = None):
                super().__init__()
                self.template = discord.ui.TextInput(
                    label="Template",
                    style=discord.TextStyle.paragraph,
                    default=default or "Welcome {user} to {guild}! We now have {membercount} members.",
                    required=True,
                    max_length=1000,
                )
                self.add_item(self.template)

            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.send_message(
                    f"Template updated in editor (not saved yet).",
                    ephemeral=True,
                )

        class WelcomeSetupView(discord.ui.View):
            def __init__(self, parent: "WelcomeCog", guild: discord.Guild, pre_channel_id: int | None, pre_message: str | None):
                super().__init__(timeout=300)
                self.parent = parent
                self.guild = guild
                self.selected_channel_id: int | None = pre_channel_id
                self.template: str | None = pre_message

            @discord.ui.select(
                cls=discord.ui.ChannelSelect,
                channel_types=[discord.ChannelType.text],
                placeholder="Select welcome channel",
                min_values=1,
                max_values=1,
            )
            async def select_channel(self, select_interaction: discord.Interaction, select: discord.ui.ChannelSelect):
                ch = select.values[0]
                self.selected_channel_id = ch.id
                await select_interaction.response.edit_message(content=f"Selected channel: {ch.mention}", view=self)

            @discord.ui.button(label="Edit Template", style=discord.ButtonStyle.primary)
            async def edit_template(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                modal = TemplateModal(default=self.template)
                await button_interaction.response.send_modal(modal)
                try:
                    modal_inter: discord.Interaction = await self.parent.bot.wait_for(
                        "interaction",
                        check=lambda i: isinstance(i, discord.Interaction) and i.user.id == button_interaction.user.id and i.type.name == "modal_submit",
                        timeout=120,
                    )
                    # Update local template from modal
                    # modal.children[0] is the TextInput
                    self.template = str(modal.children[0].value) if modal.children else self.template
                except Exception:
                    pass

            @discord.ui.button(label="Save", style=discord.ButtonStyle.success)
            async def save(self, save_interaction: discord.Interaction, button: discord.ui.Button):
                if not getattr(self.parent.bot, "pool", None):
                    await save_interaction.response.send_message("Database not configured.", ephemeral=True)
                    return
                if self.selected_channel_id is None and self.template is None:
                    await save_interaction.response.send_message("Nothing to save.", ephemeral=True)
                    return
                async with self.parent.bot.pool.acquire() as conn:
                    self.parent.log.info(
                        f"[DB] Upserting welcome config via setup guild={self.guild.id} channel={self.selected_channel_id}"
                    )
                    await conn.execute(
                        """
                        INSERT INTO general_server (guild_id, guild_name, welcome_channel_id, welcome_message)
                        VALUES ($1,$2,$3,$4)
                        ON CONFLICT (guild_id) DO UPDATE SET guild_name=EXCLUDED.guild_name,
                            welcome_channel_id=COALESCE(EXCLUDED.welcome_channel_id, general_server.welcome_channel_id),
                            welcome_message=COALESCE(EXCLUDED.welcome_message, general_server.welcome_message)
                        """,
                        self.guild.id,
                        self.guild.name,
                        self.selected_channel_id,
                        self.template,
                    )
                embed = discord.Embed(title="Welcome settings saved", color=PURPLE)
                if self.selected_channel_id:
                    ch = self.guild.get_channel(self.selected_channel_id)
                    if ch:
                        embed.add_field(name="Channel", value=ch.mention, inline=True)
                if self.template:
                    preview = (self.template[:200] + "…") if len(self.template or "") > 200 else (self.template or "")
                    embed.add_field(name="Template", value=preview or "(unchanged)", inline=False)
                embed.set_footer(text=FOOTER_TEXT)
                await save_interaction.response.send_message(embed=embed, ephemeral=True)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
                await cancel_interaction.response.edit_message(content="Setup cancelled.", view=None)

        view = WelcomeSetupView(self, interaction.guild, current_channel_id, current_message)
        content = "Configure welcome settings below. Use the selector to choose a channel and the button to edit the template, then Save."
        await interaction.response.send_message(content, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild is None:
            return
        pool = getattr(self.bot, "pool", None)
        channel_id = None
        template = None
        if pool:
            async with pool.acquire() as conn:
                self.log.info(f"[DB] Fetching welcome config for guild={member.guild.id}")
                row = await conn.fetchrow(
                    "SELECT welcome_channel_id, welcome_message FROM general_server WHERE guild_id=$1",
                    member.guild.id,
                )
                if row:
                    channel_id = row["welcome_channel_id"]
                    template = row["welcome_message"]
                    self.log.info(f"[DB] Welcome config found channel={channel_id} template={'set' if template else 'none'}")
                # Log join
                self.log.info(f"[DB] Inserting user_joins user={member.id} guild={member.guild.id}")
                await conn.execute(
                    "INSERT INTO user_joins (user_id, user_name, guild_id, guild_name) VALUES ($1,$2,$3,$4)",
                    member.id,
                    str(member),
                    member.guild.id,
                    member.guild.name,
                )
                self.log.info(f"[DB] Inserted user_joins user={member.id} guild={member.guild.id}")

        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                msg = template or "Welcome {user} to {guild}! We now have {membercount} members."
                text = msg.format(user=member.mention, guild=member.guild.name, membercount=member.guild.member_count)
                embed = discord.Embed(title=f"Welcome to {member.guild.name}!", description=text, color=PURPLE)
                # Visuals
                guild_icon = getattr(member.guild.icon, "url", None)
                embed.set_author(name=str(member), icon_url=guild_icon)
                if guild_icon:
                    embed.set_thumbnail(url=guild_icon)
                    embed.set_image(url=guild_icon)
                embed.add_field(name="Member", value=member.mention, inline=True)
                embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
                embed.timestamp = datetime.now(timezone.utc)
                embed.set_footer(text=FOOTER_TEXT)
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    self.log.warning("Failed to send welcome embed due to HTTPException")
                except Exception as e:
                    self.log.warning(f"Failed to send welcome embed: {e}")


async def setup(bot: commands.Bot) -> None:
    cog = WelcomeCog(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.group)
    except Exception:
        pass