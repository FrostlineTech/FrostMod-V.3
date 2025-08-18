# Autorole cog — assigns a configured role to users when they join (admin only)
# Ensure this cog is loaded by the main entrypoint `frostmodv3.py`
# All embeds include the standard footer and use cobalt blue (0x0047AB) via `branding.py`
# Ensure the role is assigned to the user when they join the server
#command will be /jrole <role> (admin only)
#check schema.sql for the table structure 

from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from branding import BRAND_COLOR, FOOTER_TEXT


class AutoroleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="jrole", description="Set the role to auto-assign when users join (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def jrole(self, interaction: discord.Interaction, role: discord.Role):
        if not getattr(self.bot, "pool", None):
            await interaction.response.send_message("Database not configured.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with self.bot.pool.acquire() as conn:
            self.log.info(f"[DB] Upserting join_role_id guild={interaction.guild.id} role={role.id}")
            await conn.execute(
                """
                INSERT INTO general_server (guild_id, guild_name, join_role_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO UPDATE SET guild_name = EXCLUDED.guild_name, join_role_id = EXCLUDED.join_role_id
                """,
                interaction.guild.id,
                interaction.guild.name,
                role.id,
            )
            self.log.info(f"[DB] Upserted join_role_id for guild={interaction.guild.id}")

        embed = discord.Embed(
            title="Join Role Updated",
            description=f"New members will be given the role {role.mention}.",
            color=BRAND_COLOR,
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild is None:
            return
        pool = getattr(self.bot, "pool", None)
        role_id = None
        if pool:
            async with pool.acquire() as conn:
                self.log.info(f"[DB] Fetching join_role_id for guild={member.guild.id}")
                row = await conn.fetchrow(
                    "SELECT join_role_id FROM general_server WHERE guild_id=$1",
                    member.guild.id,
                )
                if row:
                    role_id = row["join_role_id"]
                    self.log.info(f"[DB] join_role_id fetched: {role_id}")

        if role_id:
            role = member.guild.get_role(role_id)
            if role is None:
                self.log.warning(f"[ROLE] Configured role id {role_id} not found in guild {member.guild.id}")
                return
            # Check hierarchy and permissions
            me = member.guild.me
            if me is None:
                self.log.warning(f"[ROLE] Bot member not found in guild {member.guild.id}")
                return
            if not me.guild_permissions.manage_roles:
                self.log.warning(f"[ROLE] Missing Manage Roles permission in guild {member.guild.id}")
                return
            try:
                self.log.info(
                    f"[ROLE] Check: bot_top_pos={me.top_role.position if me.top_role else 'N/A'} "
                    f"target_role_pos={role.position} member_has_role={role in member.roles}"
                )
                if role < me.top_role and role not in member.roles:
                    await member.add_roles(role, reason="Autorole on join")
                    self.log.info(f"[ROLE] Assigned role {role.id} to user {member.id} in guild {member.guild.id}")
                else:
                    reason = []
                    if not (role < me.top_role):
                        reason.append("role_above_bot")
                    if role in member.roles:
                        reason.append("already_has_role")
                    self.log.info(f"[ROLE] Skipped assigning role {role.id} to user {member.id} ({','.join(reason) or 'unknown_reason'})")
            except discord.Forbidden:
                self.log.warning(f"[ROLE] Forbidden to assign role {role.id} to user {member.id} in guild {member.guild.id}")
            except discord.HTTPException:
                self.log.warning(f"[ROLE] HTTPException while assigning role {role.id} to user {member.id} in guild {member.guild.id}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoroleCog(bot))