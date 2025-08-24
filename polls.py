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
    def __init__(self, state: PollState, *, message_id: int):
        super().__init__(timeout=None)
        self.state = state
        self.message_id = message_id
        # Create a button per option (Discord allows up to 25 components; we limit options)
        for idx, label in enumerate(state.options):
            self.add_item(PollButton(idx=idx, label=label, message_id=message_id))
        # Add a results refresh button
        self.add_item(RefreshButton(message_id=message_id))
        # Add an End Poll button (admin only control, but we'll permission-check in callback)
        self.add_item(EndPollButton(message_id=message_id))

    async def on_timeout(self):
        # We don't rely on view timeout; closing handled by task
        pass


class PollButton(discord.ui.Button):
    def __init__(self, idx: int, label: str, *, message_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"poll:{message_id}:opt:{idx}")
        self.idx = idx
        self._message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view  # type: ignore
        state = view.state
        if state.closed:
            await interaction.response.send_message("This poll has closed.", ephemeral=True)
            return
        # Record/replace vote (in-memory)
        prev = state.votes.get(interaction.user.id)
        state.votes[interaction.user.id] = self.idx
        changed = "changed" if prev is not None and prev != self.idx else "recorded"
        await interaction.response.send_message(f"Your vote has been {changed}.", ephemeral=True)
        # Persist vote to DB if available
        bot = interaction.client  # commands.Bot
        pool = getattr(bot, "pool", None)
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO polls_votes (message_id, user_id, option_idx)
                        VALUES ($1,$2,$3)
                        ON CONFLICT (message_id, user_id) DO UPDATE SET option_idx=EXCLUDED.option_idx
                        """,
                        self._message_id,
                        interaction.user.id,
                        self.idx,
                    )
            except Exception:
                pass
        # Optionally update message with new tallies (lightweight refresh; avoid rate limits)
        try:
            if self._message_id and interaction.channel:
                msg = await interaction.channel.fetch_message(self._message_id)
                await msg.edit(embed=build_poll_embed(state))
        except Exception:
            pass


class RefreshButton(discord.ui.Button):
    def __init__(self, *, message_id: int):
        super().__init__(label="Refresh", style=discord.ButtonStyle.secondary, custom_id=f"poll:{message_id}:refresh")

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view  # type: ignore
        await interaction.response.edit_message(embed=build_poll_embed(view.state), view=view)


class EndPollButton(discord.ui.Button):
    def __init__(self, *, message_id: int):
        super().__init__(label="End Poll", style=discord.ButtonStyle.danger, custom_id=f"poll:{message_id}:end")
        self._message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        # Permission check: manage_guild required
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You need Manage Server to end this poll.", ephemeral=True)
            return
        view: PollView = self.view  # type: ignore
        state = view.state
        if state.closed:
            await interaction.response.send_message("Poll already closed.", ephemeral=True)
            return
        state.closed = True
        # Disable all buttons
        for item in list(view.children):
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        # Persist closed state
        bot = interaction.client
        pool = getattr(bot, "pool", None)
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE polls_active SET closed=TRUE WHERE message_id=$1", self._message_id)
            except Exception:
                pass
        # Edit message
        try:
            await interaction.response.edit_message(embed=build_poll_embed(state), view=view)
        except Exception:
            try:
                if interaction.channel:
                    msg = await interaction.channel.fetch_message(self._message_id)
                    await msg.edit(embed=build_poll_embed(state), view=view)
            except Exception:
                pass


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
        embed = build_poll_embed(state)
        # Send without view first to get the message id for deterministic custom_ids
        await interaction.response.send_message(embed=embed)
        sent = await interaction.original_response()
        state.message_id = sent.id
        view = PollView(state, message_id=sent.id)
        # Attach the view now
        await sent.edit(embed=embed, view=view)

        # Persist the poll meta and initialize storage
        bot = interaction.client
        pool = getattr(bot, "pool", None)
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO polls_active (message_id, channel_id, guild_id, question, options, closed)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        ON CONFLICT (message_id) DO UPDATE SET question=EXCLUDED.question, options=EXCLUDED.options, closed=EXCLUDED.closed
                        """,
                        sent.id,
                        interaction.channel_id,
                        interaction.guild_id or 0,
                        state.question,
                        opts,
                        False,
                    )
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
            # Persist closed
            pool = getattr(self.bot, "pool", None)
            if pool:
                try:
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE polls_active SET closed=TRUE WHERE message_id=$1", sent.id)
                except Exception:
                    pass

        asyncio.create_task(closer())

    @poll.autocomplete("duration")
    async def duration_autocomplete(self, interaction: discord.Interaction, current: str):
        suggestions = [
            ("30 seconds", "30s"),
            ("1 minute", "1m"),
            ("5 minutes", "5m"),
            ("10 minutes", "10m"),
            ("30 minutes", "30m"),
            ("1 hour", "1h"),
        ]
        cur = current.lower().strip()
        filtered = [s for s in suggestions if cur in s[1] or cur in s[0].lower()]
        return [app_commands.Choice(name=name, value=value) for name, value in (filtered or suggestions)][:25]

    async def restore_active_polls(self):
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT message_id, channel_id, guild_id, question, options, closed FROM polls_active WHERE closed=FALSE")
                for row in rows:
                    message_id = row["message_id"]
                    channel_id = row["channel_id"]
                    guild_id = row["guild_id"]
                    question = row["question"]
                    options = list(row["options"]) if row["options"] is not None else []
                    # Rebuild votes
                    votes_rows = await conn.fetch("SELECT user_id, option_idx FROM polls_votes WHERE message_id=$1", message_id)
                    votes = {int(r["user_id"]): int(r["option_idx"]) for r in votes_rows}
                    state = PollState(question=question, options=options, votes=votes, message_id=message_id, closed=False)
                    # Register a persistent view for this message id
                    self.bot.add_view(PollView(state, message_id=message_id), message_id=message_id)
        except Exception:
            pass


async def setup(bot: commands.Bot) -> None:
    cog = PollsCog(bot)
    await bot.add_cog(cog)
    # Attempt to restore active polls
    await cog.restore_active_polls()
