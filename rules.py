#this will be the new rules cog for admins to use to set rules for their server
#create a /rules command which prompts a interactive ui for admin to choose channel n then edit thier rules template
#when done the user presses save and it posts to the selected rules channel 

#ensure this cog and command is loaded in the main file frostmodv3.py

from __future__ import annotations

import logging
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


DEFAULT_TEMPLATE = (
    """
Welcome to {guild}!

1) Be respectful to everyone.
2) No harassment, hate speech, or NSFW content.
3) Follow Discord's Terms of Service.
4) Keep channels on-topic.
5) Listen to the moderators.

By participating, you agree to follow these rules.
    """.strip()
)


class RulesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="rules", description="Configure and post server rules (admin only)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def rules(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return

        class TemplateModal(discord.ui.Modal, title="Edit Rules Template"):
            def __init__(self, default: str | None = None):
                super().__init__()
                self.template = discord.ui.TextInput(
                    label="Rules Content",
                    style=discord.TextStyle.paragraph,
                    default=default or DEFAULT_TEMPLATE.format(guild=interaction.guild.name),
                    required=True,
                    max_length=4000,
                )
                self.add_item(self.template)

            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.send_message(
                    "Template updated in editor (not posted yet).",
                    ephemeral=True,
                )

        class RulesSetupView(discord.ui.View):
            def __init__(self, parent: "RulesCog", guild: discord.Guild):
                super().__init__(timeout=300)
                self.parent = parent
                self.guild = guild
                self.selected_channel_id: int | None = None
                self.template: str | None = DEFAULT_TEMPLATE.format(guild=guild.name)

            @discord.ui.select(
                cls=discord.ui.ChannelSelect,
                channel_types=[discord.ChannelType.text],
                placeholder="Select rules channel",
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
                        check=lambda i: isinstance(i, discord.Interaction)
                        and i.user.id == button_interaction.user.id
                        and i.type.name == "modal_submit",
                        timeout=180,
                    )
                    # Update from modal
                    self.template = str(modal.children[0].value) if modal.children else self.template
                except Exception:
                    pass

            @discord.ui.button(label="Save & Post", style=discord.ButtonStyle.success)
            async def save(self, save_interaction: discord.Interaction, button: discord.ui.Button):
                if self.selected_channel_id is None:
                    await save_interaction.response.send_message("Please select a rules channel first.", ephemeral=True)
                    return
                ch = self.guild.get_channel(self.selected_channel_id)
                if not isinstance(ch, discord.TextChannel):
                    await save_interaction.response.send_message("Selected destination is not a text channel.", ephemeral=True)
                    return
                # Build embed
                content = (self.template or DEFAULT_TEMPLATE).format(guild=self.guild.name)
                embed = discord.Embed(title=f"{self.guild.name} • Server Rules", description=content, color=BRAND_COLOR)
                embed.set_footer(text=FOOTER_TEXT)
                embed.timestamp = datetime.now(timezone.utc)
                try:
                    await ch.send(embed=embed)
                    await save_interaction.response.edit_message(content=f"Rules posted to {ch.mention}.", view=None)
                except discord.Forbidden:
                    await save_interaction.response.send_message("I don't have permission to post in that channel.", ephemeral=True)
                except Exception as e:
                    await save_interaction.response.send_message(f"Failed to post rules: {e}", ephemeral=True)

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
                await cancel_interaction.response.edit_message(content="Rules configuration cancelled.", view=None)

        view = RulesSetupView(self, interaction.guild)
        content = (
            "Configure your rules post. Select a channel, optionally edit the template, then 'Save & Post' to publish."
        )
        await interaction.response.send_message(content, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = RulesCog(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.rules)
    except Exception:
        pass