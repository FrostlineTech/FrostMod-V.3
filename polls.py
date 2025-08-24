from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Dict, List

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


DURATION_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", re.IGNORECASE)


def parse_duration(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    m = DURATION_RE.match(s)
    if not m:
        return None
    h = int(m.group(1) or 0)
    m_ = int(m.group(2) or 0)
    s_ = int(m.group(3) or 0)
    total = h * 3600 + m_ * 60 + s_
    return total if total > 0 else None


@dataclass
class PollState:
    question: str
    options: List[str]
    votes: Dict[int, int]  # user_id -> option_index
    message_id: int | None = None
    closed: bool = False


class PollView(discord.ui.View):
    def __init__(self, state: PollState):
        super().__init__(timeout=None)
        self.state = state
        # Create a button per option (Discord allows up to 25 components; we limit options)
        for idx, label in enumerate(state.options):
            self.add_item(PollButton(idx=idx, label=label))
        # Add a results refresh button
        self.add_item(RefreshButton())

    async def on_timeout(self):
        # We don't rely on view timeout; closing handled by task
        pass


class PollButton(discord.ui.Button):
    def __init__(self, idx: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view  # type: ignore
        state = view.state
        if state.closed:
            await interaction.response.send_message("This poll has closed.", ephemeral=True)
            return
        # Record/replace vote
        prev = state.votes.get(interaction.user.id)
        state.votes[interaction.user.id] = self.idx
        changed = "changed" if prev is not None and prev != self.idx else "recorded"
        await interaction.response.send_message(f"Your vote has been {changed}.", ephemeral=True)
        # Optionally update message with new tallies (lightweight refresh; avoid rate limits)
        try:
            if state.message_id and interaction.channel:
                msg = await interaction.channel.fetch_message(state.message_id)
                await msg.edit(embed=build_poll_embed(state))
        except Exception:
            pass


class RefreshButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view  # type: ignore
        await interaction.response.edit_message(embed=build_poll_embed(view.state), view=view)


def build_poll_embed(state: PollState) -> discord.Embed:
    # Tally counts
    counts = [0] * len(state.options)
    for _, idx in state.votes.items():
        if 0 <= idx < len(counts):
            counts[idx] += 1
    total = sum(counts)
    lines = []
    for i, (opt, c) in enumerate(zip(state.options, counts)):
        pct = 0 if total == 0 else int(round(c * 100 / total))
        bar_len = 10
        filled = 0 if total == 0 else int(round(pct / 10))
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"{i+1}. {opt} — **{c}** ({pct}%)  {bar}")
    desc = "\n".join(lines)
    title = ("Poll (Closed)" if state.closed else "Poll")
    embed = discord.Embed(title=title, description=desc, color=BRAND_COLOR)
    embed.add_field(name="Question", value=state.question, inline=False)
    if total:
        embed.set_footer(text=f"{FOOTER_TEXT} • {total} vote(s)")
    else:
        embed.set_footer(text=FOOTER_TEXT)
    return embed


class PollsCog(commands.Cog):
    """Create interactive button polls (admin only for creation)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create an interactive poll (admin only)")
    @app_commands.describe(
        question="The poll question",
        options="Semicolon-separated options, e.g. 'A;B;C' (max 10)",
        duration="How long the poll lasts (e.g., 10m, 1h, 90s)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def poll(self, interaction: discord.Interaction, question: str, options: str, duration: str = "10m"):
        # Parse inputs
        opts = [o.strip() for o in options.split(";") if o.strip()]
        if not (2 <= len(opts) <= 10):
            await interaction.response.send_message("Please provide between 2 and 10 options (use ';' to separate).", ephemeral=True)
            return
        seconds = parse_duration(duration)
        if seconds is None:
            await interaction.response.send_message("Invalid duration. Try formats like '10m', '1h', '45s', or seconds.", ephemeral=True)
            return

        state = PollState(question=question.strip(), options=opts, votes={})
        view = PollView(state)
        embed = build_poll_embed(state)
        await interaction.response.send_message(embed=embed, view=view)
        try:
            sent = await interaction.original_response()
            state.message_id = sent.id
        except Exception:
            pass

        async def closer():
            await asyncio.sleep(seconds)
            state.closed = True
            # Disable buttons
            for item in list(view.children):
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            # Edit message with final results
            try:
                await sent.edit(embed=build_poll_embed(state), view=view)
            except Exception:
                pass

        asyncio.create_task(closer())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PollsCog(bot))
