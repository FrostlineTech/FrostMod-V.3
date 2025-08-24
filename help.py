from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from branding import BRAND_COLOR, FOOTER_TEXT
from ui import make_embed


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="help", description="Admin help: interactive guide for FrostMod features")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def help_cmd(self, interaction: discord.Interaction):
        view = HelpView()
        embed = help_category_embed("setup", interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(HelpSelect())


class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Setup", value="setup", description="Quick start to configure core features"),
            discord.SelectOption(label="Logging", value="logging", description="Configure logs channel and toggles"),
            discord.SelectOption(label="Public Info", value="public", description="/about and /commands"),
            discord.SelectOption(label="Utilities", value="utilities", description="Avatars, banners, userinfo"),
            discord.SelectOption(label="Games", value="games", description="RPS, TicTacToe, Connect4"),
            discord.SelectOption(label="Troubleshooting", value="troubleshoot", description="Fix common issues"),
            discord.SelectOption(label="Templates", value="templates", description="Placeholders for messages"),
            discord.SelectOption(label="Permissions", value="perms", description="Required permissions checklist"),
        ]
        super().__init__(placeholder="Select a help category…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):  # type: ignore[override]
        value = self.values[0]
        embed = help_category_embed(value, interaction)
        await interaction.response.edit_message(embed=embed, view=self.view)


def help_category_embed(category: str, interaction: discord.Interaction) -> discord.Embed:
    if category == "setup":
        desc = (
            "1) `/welcome setup` — choose channel + template\n"
            "2) `/leave setup` — choose channel + template\n"
            "3) `/logs` — pick logs channel, toggle deletes/edits/joins\n"
            "4) `/jrole <@role>` — set autorole (ensure bot role is higher)\n"
            "5) `/poll` — create a poll (admin only)\n"
            "6) `/status`, `/db` — diagnostics"
        )
        return make_embed(title="Admin Help — Setup", description=desc, interaction=interaction)
    if category == "logging":
        desc = (
            "Open `/logs` (Manage Server). Choose a logs channel and toggle items.\n"
            "Supports: deleted messages, edits, joins/leaves; nickname/role/avatar changes.\n"
            "Note: Some features require Message Content intent and View Audit Log."
        )
        return make_embed(title="Admin Help — Logging", description=desc, interaction=interaction)
    if category == "public":
        desc = "`/about` — About FrostMod (ephemeral).\n`/commands` — Member commands list (ephemeral)."
        return make_embed(title="Admin Help — Public Info", description=desc, interaction=interaction)
    if category == "utilities":
        desc = "`/avatar`, `/banner`, `/userinfo` — quick user utilities with buttons."
        return make_embed(title="Admin Help — Utilities", description=desc, interaction=interaction)
    if category == "games":
        desc = "`/rps`, `/tictactoe`, `/connect4` — interactive buttons; `/meme`, `/caption`, `/dadjoke`."
        return make_embed(title="Admin Help — Games & Fun", description=desc, interaction=interaction)
    if category == "templates":
        desc = (
            "Placeholders: `{user}` (mention), `{guild}`, `{membercount}`.\n"
            "Example: `Welcome {user} to {guild}! We now have {membercount} members.`"
        )
        return make_embed(title="Admin Help — Templates", description=desc, interaction=interaction)
    if category == "perms":
        desc = (
            "• Manage Guild required for admin commands.\n"
            "• Bot needs Send Messages + Embed Links in target channels.\n"
            "• For autorole, bot's highest role must be above target role."
        )
        return make_embed(title="Admin Help — Permissions", description=desc, interaction=interaction)
    if category == "troubleshoot":
        desc = (
            "• Commands missing: wait for sync; dev guild sync is instant.\n"
            "• DB errors: verify .env DB settings/connectivity.\n"
            "• Role not applied: check role hierarchy + Manage Roles.\n"
            "• Use `/status` and `/db` for diagnostics."
        )
        return make_embed(title="Admin Help — Troubleshooting", description=desc, interaction=interaction)
    return make_embed(title="Admin Help", description="Select a category.", interaction=interaction)


async def setup(bot: commands.Bot) -> None:
    cog = HelpCog(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.help_cmd)
    except Exception:
        pass
