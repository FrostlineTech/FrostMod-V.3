from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from branding import BRAND_COLOR, FOOTER_TEXT, GREEN, YELLOW, RED

class AIHelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))

    @app_commands.command(name="aihelp", description="Admin help: guide for AI moderation features")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def aihelp_cmd(self, interaction: discord.Interaction):
        view = AIHelpView()
        embed = ai_help_category_embed("overview", interaction)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AIHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(AIHelpSelect())


class AIHelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview", value="overview", description="What is AI moderation and how it works"),
            discord.SelectOption(label="Commands", value="commands", description="AI moderation commands reference"),
            discord.SelectOption(label="Settings", value="settings", description="Configuring AI moderation parameters"),
            discord.SelectOption(label="Monitoring", value="monitoring", description="Viewing AI moderation stats and activity"),
            discord.SelectOption(label="Appeals", value="appeals", description="How users can appeal moderation actions"),
            discord.SelectOption(label="Optimization", value="optimization", description="Hardware optimization for AI performance"),
            discord.SelectOption(label="Troubleshooting", value="troubleshoot", description="Fix common AI moderation issues"),
        ]
        super().__init__(placeholder="Select a help category…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        embed = ai_help_category_embed(value, interaction)
        await interaction.response.edit_message(embed=embed, view=self.view)


def ai_help_category_embed(category: str, interaction: discord.Interaction) -> discord.Embed:
    if category == "overview":
        desc = (
            "FrostMod's AI moderation automatically detects and removes inappropriate content using a local "
            "DeepSeek model.\n\n"
            "**Key features:**\n"
            "• Real-time content moderation with customizable strictness\n"
            "• Channel-specific moderation settings with `/channelmod`\n"
            "• Pattern recognition to detect content split across messages\n"
            "• Advanced user profiling and risk assessment\n"
            "• AI-powered help system with `/ask` and `/askabout` commands\n"
            "• User feedback mechanism for flagged messages\n"
            "• Full appeal process with mod review\n"
            "• Hardware optimization for efficient inference\n"
            "• Detailed logging and performance monitoring"
        )
        embed = discord.Embed(title="AI Moderation — Overview", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
        
    if category == "commands":
        desc = (
            "**Admin Commands:**\n"
            "• `/aimod` — Configure AI moderation settings with a user-friendly UI\n"
            "• `/testmod <message>` — Test the AI moderation on a sample message\n"
            "• `/modstats` — View AI moderation statistics and performance metrics\n\n"
            "**User Features:**\n"
            "• Feedback buttons on moderation warnings\n"
            "• Appeal process for flagged messages\n"
            "• Direct notifications for appeal decisions"
        )
        embed = discord.Embed(title="AI Moderation — Commands", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
        
    if category == "settings":
        desc = (
            "Configure AI moderation with `/aimod` command:\n\n"
            "**Server Settings:**\n"
            "• **Enable/Disable** — Toggle AI moderation for the server\n"
            "• **Temperature** — Set strictness level (lower = stricter)\n"
            "   - `Low (0.2-0.3)`: Very strict, catches most violations\n"
            "   - `Medium (0.4-0.6)`: Balanced approach\n"
            "   - `High (0.7-0.8)`: More lenient, fewer false positives\n\n"
            "**Channel-Specific Settings** with `/channelmod [#channel]`:\n"
            "• Override server settings for specific channels\n"
            "• Set different strictness levels per channel\n"
            "• Perfect for NSFW channels, support channels, or mod-only areas\n\n"
            "**Other Settings:**\n"
            "• **Warning Duration** — How long warning messages display\n"
            "• **Confidence Threshold** — Minimum confidence for action"
        )
        embed = discord.Embed(title="AI Moderation — Settings", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
    
    if category == "monitoring":
        desc = (
            "**Monitoring AI Performance:**\n"
            "• `/modstats` — View detailed performance metrics\n"
            "• Messages analyzed and flagged count\n"
            "• Average inference time\n"
            "• Hardware utilization stats\n\n"
            "**User Profiling and Risk Assessment:**\n"
            "• `/risklevel <@user>` — Get AI-based risk assessment\n"
            "• Analysis includes message patterns, activity timing, join behavior\n"
            "• Social connection mapping across shared servers\n"
            "• Automated anomaly detection\n\n"
            "**Logs:**\n"
            "• All moderation actions are logged to your server's logs channel\n"
            "• Includes message content, confidence score, and reason\n"
            "• Appeal submissions and decisions are also logged"
        )
        embed = discord.Embed(title="AI Moderation — Monitoring", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
    
    if category == "appeals":
        desc = (
            "**How Appeals Work:**\n"
            "1. User clicks \"This was wrong\" button on moderation warning\n"
            "2. User fills out appeal form explaining why message should not have been removed\n"
            "3. Appeal is sent to server's logs channel with approve/deny buttons\n"
            "4. Moderators review and make decision\n"
            "5. User is notified of the outcome via DM\n\n"
            "Appeals help improve moderation accuracy and provide fair recourse for users."
        )
        embed = discord.Embed(title="AI Moderation — Appeals", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
    
    if category == "optimization":
        desc = (
            "**Hardware Optimization:**\n"
            "The AI moderation system automatically detects and optimizes for your hardware:\n\n"
            "• **NVIDIA GPU** (optimized for RTX 3060):\n"
            "  - Automatic batch size adjustment\n"
            "  - CUDA acceleration\n"
            "  - Memory optimization for 12GB VRAM\n\n"
            "• **CPU Mode:**\n"
            "  - Multi-threading optimization\n"
            "  - Reduced precision for faster inference"
        )
        embed = discord.Embed(title="AI Moderation — Optimization", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
    
    if category == "troubleshoot":
        desc = (
            "**Common Issues:**\n"
            "• **AI not responding** — Check your local model API is running\n"
            "• **Slow inference** — Consider GPU acceleration or lower temperature\n"
            "• **Too many false positives** — Increase temperature threshold\n"
            "• **Missing violations** — Lower temperature threshold\n"
            "• **Database errors** — Verify DB connection in your .env file\n\n"
            "Use `/testmod` to verify your settings with sample messages."
        )
        embed = discord.Embed(title="AI Moderation — Troubleshooting", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed
    
    # Default case
    embed = discord.Embed(title="AI Moderation Help", description="Select a category to learn more.", color=BRAND_COLOR)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


async def setup(bot: commands.Bot) -> None:
    cog = AIHelpCog(bot)
    await bot.add_cog(cog)
    try:
        bot.tree.add_command(cog.aihelp_cmd)
    except Exception:
        pass
