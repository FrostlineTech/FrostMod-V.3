from __future__ import annotations

import json
import io
import logging
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT, YELLOW, GREEN, RED
from ui import make_embed


ALLOWED_KEYS = {
    "join_role_id",
    "welcome_channel_id",
    "leave_channel_id",
    "welcome_message",
    "leave_message",
    "logs_channel_id",
    "log_message_delete",
    "log_nickname_change",
    "log_role_change",
    "log_avatar_change",
    "log_message_edit",
    "log_member_join",
    "log_member_leave",
    "log_voice_join",
    "log_voice_leave",
    "digest_channel_id",
}


class SettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="settings_export", description="Export FrostMod server settings as JSON")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def settings_export(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "pool", None)
        if not pool or not interaction.guild:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM general_server WHERE guild_id=$1", interaction.guild.id)
            data = dict(row) if row else {"guild_id": interaction.guild.id, "guild_name": interaction.guild.name}
            # Filter to allowed
            out = {k: v for k, v in data.items() if k in ALLOWED_KEYS}
            payload = json.dumps(out, indent=2)
        file = discord.File(fp=io.BytesIO(payload.encode("utf-8")), filename=f"frostmod-settings-{interaction.guild.id}.json")
        await interaction.response.send_message(content="Here are your settings:", file=file, ephemeral=True)

    @app_commands.command(name="settings_import", description="Import settings from a JSON attachment URL (admin only)")
    @app_commands.describe(url="Direct URL to a JSON file with settings")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def settings_import(self, interaction: discord.Interaction, url: str):
        if not interaction.guild:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        pool = getattr(self.bot, "pool", None)
        if not pool:
            await interaction.response.send_message("Database not available.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Fetch JSON
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch JSON: {e}", ephemeral=True)
            return

        if not isinstance(data, dict):
            await interaction.followup.send("Invalid JSON structure.", ephemeral=True)
            return

        changes = {k: v for k, v in data.items() if k in ALLOWED_KEYS}
        if not changes:
            await interaction.followup.send("No supported keys found in JSON.", ephemeral=True)
            return

        # Build preview
        preview_lines = [f"• {k}: {v}" for k, v in changes.items()]
        embed = make_embed(title="Import Settings — Preview", description="\n".join(preview_lines), interaction=interaction, color=YELLOW)

        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.confirmed = False

            @discord.ui.button(label="Apply", style=discord.ButtonStyle.success)
            async def apply(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                self.confirmed = True
                await btn_inter.response.defer(ephemeral=True)
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                await btn_inter.response.edit_message(content="Import cancelled.", view=None)
                self.stop()

        view = ConfirmView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        timeout = await view.wait()
        if not view.confirmed:
            return

        # Apply changes
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO general_server (guild_id, guild_name) VALUES ($1,$2) ON CONFLICT (guild_id) DO NOTHING", interaction.guild.id, interaction.guild.name)
            sets = ", ".join([f"{k}=${i+1}" for i, k in enumerate(changes.keys())])
            values = list(changes.values())
            values.extend([interaction.guild.id])
            await conn.execute(f"UPDATE general_server SET {sets} WHERE guild_id=${len(values)}", *values)

        await interaction.followup.send(embed=make_embed(title="Settings applied", description="Import complete.", interaction=interaction, color=GREEN), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SettingsCog(bot))
