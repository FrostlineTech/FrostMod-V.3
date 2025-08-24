from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT
from ui import make_embed


class SetupWizard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Open the FrostMod setup wizard")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def setup_cmd(self, interaction: discord.Interaction):
        embed = make_embed(
            title="FrostMod Setup Wizard",
            description=(
                "Use the buttons below to open each setup flow or run diagnostics.\n"
                "• Welcome Setup — /welcome setup\n"
                "• Leave Setup — /leave setup\n"
                "• Autorole Setup — /autorole setup\n"
                "• Diagnostics — /diagnose\n"
            ),
            interaction=interaction,
        )

        class SetupView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)

            @discord.ui.button(label="Run Diagnostics", style=discord.ButtonStyle.primary, custom_id="setup:diagnostics")
            async def diag(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                await btn_inter.response.send_message("Run /diagnose to check permissions and configuration.", ephemeral=True)

            @discord.ui.button(label="Open Welcome Setup", style=discord.ButtonStyle.secondary, custom_id="setup:welcome")
            async def welcome(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                await btn_inter.response.send_message("Open `/welcome setup` to configure Welcome messages.", ephemeral=True)

            @discord.ui.button(label="Open Leave Setup", style=discord.ButtonStyle.secondary, custom_id="setup:leave")
            async def leave(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                await btn_inter.response.send_message("Open `/leave setup` to configure Leave messages.", ephemeral=True)

            @discord.ui.button(label="Open Autorole Setup", style=discord.ButtonStyle.secondary, custom_id="setup:autorole")
            async def autorole(self, btn_inter: discord.Interaction, _: discord.ui.Button):
                await btn_inter.response.send_message("Open `/autorole setup` to configure autoroles.", ephemeral=True)

        view = SetupView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupWizard(bot))
