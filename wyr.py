from __future__ import annotations

import random
import datetime
import time

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT

PROMPTS = [
    ("Have unlimited time", "Have unlimited money"),
    ("Be able to fly", "Be invisible"),
    ("Live without music", "Live without movies"),
    ("Read minds", "See the future"),
    ("Travel the world", "Own your dream home"),
]


def _bar(count: int, total: int, width: int = 12) -> str:
    if total <= 0:
        return "░" * width
    filled = int(round((count / total) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


class WYRView(discord.ui.View):
    def __init__(self, game_id: int, a: str, b: str, count_a: int, count_b: int):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.a = a
        self.b = b
        self.count_a = count_a
        self.count_b = count_b
        self.add_item(WYRButton(label=a, which="A", game_id=game_id))
        self.add_item(WYRButton(label=b, which="B", game_id=game_id))
        self.add_item(WYRRematchButton(game_id, a, b))

    def build_embed(self, *, time_left: int | None = None) -> discord.Embed:
        total = self.count_a + self.count_b
        bar_a = _bar(self.count_a, total)
        bar_b = _bar(self.count_b, total)
        desc = (
            f"A) {self.a}\n{bar_a}  {self.count_a}\n"
            f"B) {self.b}\n{bar_b}  {self.count_b}"
        )
        if time_left is not None:
            desc += f"\nTime left: {time_left}s"
        embed = discord.Embed(title="Would You Rather...", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        return embed


class WYRButton(discord.ui.Button):
    def __init__(self, label: str, which: str, game_id: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"wyr:{game_id}:{which}")
        self.which = which
        self.game_id = game_id
        self._last_by_user: dict[int, float] = {}

    async def callback(self, interaction: discord.Interaction):
        # 2s per-user cooldown to avoid double taps
        now = time.monotonic()
        last = self._last_by_user.get(interaction.user.id, 0.0)
        if now - last < 2.0:
            await interaction.response.send_message("Please wait a moment before voting again.", ephemeral=True)
            return
        self._last_by_user[interaction.user.id] = now
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            row = await conn.fetchrow(
                "SELECT prompt_a, prompt_b, count_a, count_b, finished FROM games_wyr WHERE game_id=$1",
                self.game_id,
            )
        if not row:
            await interaction.response.send_message("Game not found.", ephemeral=True)
            return
        a, b, count_a, count_b, finished = str(row[0]), str(row[1]), int(row[2]), int(row[3]), bool(row[4])
        if finished:
            await interaction.response.send_message("This poll has finished.", ephemeral=True)
            return
        # Prevent multiple votes per user
        async with pool.acquire() as conn:  # type: ignore
            async with conn.transaction():
                already = await conn.fetchval(
                    "SELECT 1 FROM games_wyr_votes WHERE game_id=$1 AND user_id=$2",
                    self.game_id,
                    interaction.user.id,
                )
                if already:
                    await interaction.response.send_message("You already voted in this poll.", ephemeral=True)
                    return
                # Record vote and update counters
                await conn.execute(
                    "INSERT INTO games_wyr_votes (game_id, user_id, choice) VALUES ($1,$2,$3)",
                    self.game_id,
                    interaction.user.id,
                    self.which,
                )
                if self.which == "A":
                    count_a += 1
                else:
                    count_b += 1
                await conn.execute(
                    "UPDATE games_wyr SET count_a=$1, count_b=$2 WHERE game_id=$3",
                    count_a,
                    count_b,
                    self.game_id,
                )
        view = WYRView(self.game_id, a, b, count_a, count_b)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
        # Offer ephemeral 10s undo
        await interaction.followup.send(
            content=f"You voted {self.which}.",
            view=WYRUndoView(self.game_id, self.which),
            ephemeral=True,
        )


class WYRUndoView(discord.ui.View):
    def __init__(self, game_id: int, which: str):
        super().__init__(timeout=10)
        self.add_item(WYRUndoButton(game_id, which))


class WYRUndoButton(discord.ui.Button):
    def __init__(self, game_id: int, which: str):
        super().__init__(label="Undo vote", style=discord.ButtonStyle.secondary, custom_id=f"wyr_undo:{game_id}:{which}")
        self.game_id = game_id
        self.which = which

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            # Only allow undo if vote exists and is recent (<=10s)
            row = await conn.fetchrow(
                "SELECT choice, created_at FROM games_wyr_votes WHERE game_id=$1 AND user_id=$2",
                self.game_id,
                interaction.user.id,
            )
            if not row:
                await interaction.response.send_message("No vote to undo.", ephemeral=True)
                return
            choice = str(row[0])
            created_at = row[1]
            from datetime import timezone, datetime, timedelta
            now = datetime.now(timezone.utc)
            if now - created_at > timedelta(seconds=10):
                await interaction.response.send_message("Undo window expired.", ephemeral=True)
                return
            a_b = await conn.fetchrow("SELECT prompt_a, prompt_b, count_a, count_b FROM games_wyr WHERE game_id=$1", self.game_id)
            a, b, count_a, count_b = str(a_b[0]), str(a_b[1]), int(a_b[2]), int(a_b[3])
            async with conn.transaction():
                await conn.execute("DELETE FROM games_wyr_votes WHERE game_id=$1 AND user_id=$2", self.game_id, interaction.user.id)
                if choice == 'A':
                    count_a = max(0, count_a - 1)
                else:
                    count_b = max(0, count_b - 1)
                await conn.execute("UPDATE games_wyr SET count_a=$1, count_b=$2 WHERE game_id=$3", count_a, count_b, self.game_id)
        # Update main (original) poll message, not the ephemeral undo message
        view = WYRView(self.game_id, a, b, count_a, count_b)
        pool = getattr(interaction.client, "pool", None)
        try:
            async with pool.acquire() as conn:  # type: ignore
                row2 = await conn.fetchrow(
                    "SELECT message_id, channel_id FROM games_wyr WHERE game_id=$1",
                    self.game_id,
                )
            if row2:
                msg_id = int(row2[0]); ch_id = int(row2[1])
                channel = interaction.client.get_channel(ch_id)
                if channel is None:
                    try:
                        channel = await interaction.client.fetch_channel(ch_id)
                    except Exception:
                        channel = None
                if isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                    try:
                        orig = await channel.fetch_message(msg_id)
                        await orig.edit(embed=view.build_embed(), view=view)
                    except Exception:
                        pass
        except Exception:
            pass
        await interaction.response.send_message("Your vote was undone.", ephemeral=True)


class WYRRematchButton(discord.ui.Button):
    def __init__(self, game_id: int, a: str, b: str):
        super().__init__(label="Rematch", style=discord.ButtonStyle.secondary, custom_id=f"wyr_rematch:{game_id}")
        self.game_id = game_id
        self.a = a
        self.b = b

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(interaction.client, "pool", None)
        a, b = self.a, self.b
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_wyr (guild_id, channel_id, message_id, prompt_a, prompt_b, count_a, count_b, finished) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                a,
                b,
                0,
                0,
                False,
            )
            new_game_id = int(rec[0])
        view = WYRView(new_game_id, a, b, 0, 0)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        msg = await interaction.original_response()
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_wyr SET message_id=$1 WHERE game_id=$2", msg.id, new_game_id)


class WYRCog(commands.Cog):
    """Would You Rather voting game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="wyr", description="Start a 'Would You Rather' poll")
    async def wyr(self, interaction: discord.Interaction):
        a, b = random.choice(PROMPTS)
        pool = getattr(self.bot, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_wyr (guild_id, channel_id, message_id, prompt_a, prompt_b, count_a, count_b, finished) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                a,
                b,
                0,
                0,
                False,
            )
            game_id = int(rec[0])
        total_secs = 120
        view = WYRView(game_id, a, b, 0, 0)
        await interaction.response.send_message(embed=view.build_embed(time_left=total_secs), view=view)
        msg = await interaction.original_response()
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_wyr SET message_id=$1 WHERE game_id=$2", msg.id, game_id)

        async def countdown_task():
            nonlocal total_secs
            try:
                while total_secs > 0:
                    await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
                    total_secs = max(0, total_secs - 5)
                    # Pull latest counts/finished
                    async with pool.acquire() as conn:  # type: ignore
                        row = await conn.fetchrow(
                            "SELECT prompt_a, prompt_b, count_a, count_b, finished FROM games_wyr WHERE game_id=$1",
                            game_id,
                        )
                    if not row:
                        return
                    a2, b2, ca2, cb2, finished = str(row[0]), str(row[1]), int(row[2]), int(row[3]), bool(row[4])
                    if finished:
                        return
                    v2 = WYRView(game_id, a2, b2, ca2, cb2)
                    try:
                        await msg.edit(embed=v2.build_embed(time_left=total_secs), view=v2)
                    except Exception:
                        pass
                # Time up: finalize if not finished
                async with pool.acquire() as conn:  # type: ignore
                    row = await conn.fetchrow(
                        "SELECT prompt_a, prompt_b, count_a, count_b, finished FROM games_wyr WHERE game_id=$1",
                        game_id,
                    )
                if row and not bool(row[4]):
                    a3, b3, ca3, cb3 = str(row[0]), str(row[1]), int(row[2]), int(row[3])
                    async with pool.acquire() as conn:  # type: ignore
                        await conn.execute("UPDATE games_wyr SET finished=TRUE WHERE game_id=$1", game_id)
                    vdone = WYRView(game_id, a3, b3, ca3, cb3)
                    for c in vdone.children:
                        if isinstance(c, discord.ui.Button):
                            c.disabled = True
                    efin = vdone.build_embed(time_left=0)
                    efin.title = "Would You Rather — Closed"
                    try:
                        await msg.edit(embed=efin, view=vdone)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            self.bot.loop.create_task(countdown_task())
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(WYRCog(bot))
    # Restore unfinished WYR polls
    pool = getattr(bot, "pool", None)
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT game_id, message_id, prompt_a, prompt_b, count_a, count_b FROM games_wyr WHERE finished=FALSE")
        for r in rows:
            gid = int(r[0]); mid = int(r[1]); a = str(r[2]); b = str(r[3]); ca = int(r[4]); cb = int(r[5])
            try:
                bot.add_view(WYRView(gid, a, b, ca, cb), message_id=mid)
            except Exception:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE games_wyr SET finished=TRUE WHERE game_id=$1", gid)
