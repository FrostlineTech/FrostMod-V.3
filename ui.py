from __future__ import annotations

import discord
from branding import BRAND_COLOR, FOOTER_TEXT


def make_embed(
    *,
    title: str | None = None,
    description: str | None = None,
    color: int | None = None,
    interaction: discord.Interaction | None = None,
    author_user: discord.abc.User | None = None,
    guild_thumbnail: bool = True,
    timestamp: bool = True,
) -> discord.Embed:
    """Create a standardized embed using brand styling.

    - Defaults to BRAND_COLOR.
    - Adds FOOTER_TEXT.
    - Optionally sets timestamp.
    - Optionally sets author and guild icon thumbnail.
    """
    embed = discord.Embed(title=title or discord.Embed.Empty, description=description or discord.Embed.Empty, color=color or BRAND_COLOR)
    if timestamp:
        embed.timestamp = discord.utils.utcnow()
    embed.set_footer(text=FOOTER_TEXT)

    # Author and thumbnail polish
    if author_user is not None:
        icon = getattr(getattr(author_user, "avatar", None), "url", None)
        embed.set_author(name=str(author_user), icon_url=icon)

    if guild_thumbnail and interaction and interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    return embed


class CopyIdButton(discord.ui.Button):
    def __init__(self, id_to_copy: int, *, label: str = "Copy ID"):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self._id_value = id_to_copy

    async def callback(self, interaction: discord.Interaction):  # type: ignore[override]
        await interaction.response.send_message(f"ID: `{self._id_value}`", ephemeral=True)


class PaginatorView(discord.ui.View):
    """Reusable paginator for a sequence of embeds.

    Usage:
        view = PaginatorView(pages=[embed1, embed2, ...])
        await interaction.response.send_message(embed=view.current, view=view, ephemeral=True)
    """

    def __init__(self, pages: list[discord.Embed], *, timeout: float | None = 180, start_index: int = 0):
        super().__init__(timeout=timeout)
        self.pages = pages if pages else [discord.Embed(description="Nothing to display.")]
        self.index = max(0, min(start_index, len(self.pages) - 1))

    @property
    def current(self) -> discord.Embed:
        return self.pages[self.index]

    async def update(self, interaction: discord.Interaction):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = len(self.pages) <= 1
        await interaction.response.edit_message(embed=self.current, view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = 0
        await self.update(interaction)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = (self.index - 1) % len(self.pages)
        await self.update(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = (self.index + 1) % len(self.pages)
        await self.update(interaction)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.index = len(self.pages) - 1
        await self.update(interaction)

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.edit_message(view=None)
