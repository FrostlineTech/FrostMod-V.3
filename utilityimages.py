from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class UtilityImages(commands.Cog):
    """User utilities: avatar, banner, and userinfo with quick-action buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="avatar", description="Show a user's avatar")
    @app_commands.describe(user="Target user (optional)")
    async def avatar(self, interaction: discord.Interaction, user: discord.User | None = None):
        user = user or interaction.user
        embed = discord.Embed(title=f"{user} — Avatar", color=BRAND_COLOR)
        if user.avatar:
            embed.set_image(url=user.avatar.url)
        else:
            embed.description = "No custom avatar. Showing default."  # Discord may still show default
        embed.set_footer(text=FOOTER_TEXT)

        view = discord.ui.View()
        if user.avatar:
            view.add_item(discord.ui.Button(label="Open", url=user.avatar.url))
        view.add_item(_CopyIdButton(user_id=user.id))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="banner", description="Show a user's banner (if available)")
    @app_commands.describe(user="Target user (optional)")
    async def banner(self, interaction: discord.Interaction, user: discord.User | None = None):
        user = user or interaction.user
        # Need to fetch to ensure banner is available
        try:
            fetched = await self.bot.fetch_user(user.id)
        except Exception:
            fetched = user
        banner = getattr(fetched, "banner", None)
        embed = discord.Embed(title=f"{user} — Banner", color=BRAND_COLOR)
        if banner:
            embed.set_image(url=banner.url)
        else:
            embed.description = "No banner set."
        embed.set_footer(text=FOOTER_TEXT)

        view = discord.ui.View()
        if banner:
            view.add_item(discord.ui.Button(label="Open", url=banner.url))
        view.add_item(_CopyIdButton(user_id=user.id))
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="userinfo", description="Show basic info about a user")
    @app_commands.describe(user="Target user (optional)")
    @app_commands.guild_only()
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member | None = None):
        member = user or interaction.user  # type: ignore[assignment]
        assert interaction.guild is not None
        # Try to get Member object
        if not isinstance(member, discord.Member):
            try:
                member = await interaction.guild.fetch_member(member.id)  # type: ignore[arg-type]
            except Exception:
                pass

        embed = discord.Embed(title=f"User Info — {member}", color=BRAND_COLOR)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Joined", value=discord.utils.format_dt(getattr(member, 'joined_at', None) or discord.utils.utcnow(), style="F"), inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(member.created_at, style="F"), inline=True)
        if isinstance(member, discord.Member):
            embed.add_field(name="Top Role", value=getattr(member.top_role, 'mention', 'None'), inline=True)
            embed.add_field(name="Roles", value=str(len(member.roles)-1), inline=True)
        embed.set_footer(text=FOOTER_TEXT)

        view = discord.ui.View()
        if member.avatar:
            view.add_item(discord.ui.Button(label="Open Avatar", url=member.avatar.url))
        banner_url = None
        try:
            fetched = await self.bot.fetch_user(member.id)
            if fetched.banner:
                banner_url = fetched.banner.url
        except Exception:
            pass
        if banner_url:
            view.add_item(discord.ui.Button(label="Open Banner", url=banner_url))
        view.add_item(_CopyIdButton(user_id=member.id))

        await interaction.response.send_message(embed=embed, view=view)


class _CopyIdButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(label="Copy ID", style=discord.ButtonStyle.secondary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"User ID: `{self.user_id}`", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilityImages(bot))
