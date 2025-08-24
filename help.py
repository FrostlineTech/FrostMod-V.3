from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from branding import BRAND_COLOR, FOOTER_TEXT


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="help", description="Admin help: how to set up FrostMod features")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="FrostMod Admin Help", color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        embed.add_field(
            name="Setup (Quick Start)",
            value=(
                "1) Configure Welcome: `/welcome setup` (choose channel + template)\n"
                "2) Configure Leave: `/leave setup` (choose channel + template)\n"
                "3) Configure Logs: `/logs` (select logs channel, toggle items incl. deletes/edits/joins)\n"
                "4) Set Autorole: `/jrole <@role>` (ensure bot role is above the target)\n"
                "5) Create a Poll: `/poll question:\"Your question\" options:\"A;B;C\" duration:10m` (admin only)\n"
                "6) Test diagnostics: `/status` and `/db`\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Public Info",
            value=(
                "- `/about` — About FrostMod, privacy, support link (ephemeral).\n"
                "- `/commands` — Lists common member commands (ephemeral).\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Logging",
            value=(
                "Use `/logs` to open an interactive panel (Manage Server required). Choose a logs channel and toggle what gets logged.\n"
                "Supported: Deleted messages, Message edits, Member joins/leaves; User changes — nickname, roles, avatar.\n"
                "Note: Some features require Message Content intent and View Audit Log permission."
            ),
            inline=False,
        )
        embed.add_field(
            name="Member Commands (Highlights)",
            value=(
                "- `/serverinfo` — Server stats.\n"
                "- `/webstatus` — Check site status.\n"
                "- `/activity` — User activity (week/month/all).\n"
                "- `/avatar`, `/banner`, `/userinfo` — Quick user utilities.\n"
                "- `/rps`, `/tictactoe`, `/connect4` — Mini games (buttons).\n"
                "- `/meme`, `/caption` — Meme fun (random or captioned).\n"
                "- `/dadjoke` — Lighten the mood."
            ),
            inline=False,
        )
        embed.add_field(
            name="Rules (/rules)",
            value=(
                "Use `/rules` (Manage Server required) to configure and post your server rules.\n"
                "Steps: Select a channel → Edit Template (optional) → Save & Post.\n"
                "Template supports `{guild}` placeholder and posts an embed titled 'Server Rules'."
            ),
            inline=False,
        )
        embed.add_field(
            name="Templates",
            value=(
                "Placeholders: `{user}` (mention), `{guild}`, `{membercount}`.\n"
                "Example: `Welcome {user} to {guild}! We now have {membercount} members.`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Permissions",
            value=(
                "- Manage Guild required for admin commands.\n"
                "- Bot needs Send Messages, Embed Links in target channels.\n"
                "- For autorole, bot's highest role must be ABOVE the target role."
            ),
            inline=False,
        )
        embed.add_field(
            name="Troubleshooting",
            value=(
                "- Commands not showing: wait for sync; dev guild sync is instant.\n"
                "- DB errors: verify `.env` DB settings and connectivity.\n"
                "- Role not applied: check role hierarchy and Manage Roles permission.\n"
                "- Use `/status` and `/db` for quick diagnostics."
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = HelpCog(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.help_cmd)
    except Exception:
        pass
