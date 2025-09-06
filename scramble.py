from __future__ import annotations

import random
import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT

WORDS = [
    "python", "discord", "frostmod", "moderation", "database", "asyncio", "channel", "message",
    "support", "heartbeat", "logging", "reaction", "webstatus", "embed", "audit"
]


def scramble_word(word: str) -> str:
    chars = list(word)
    # ensure different order when possible
    for _ in range(5):
        random.shuffle(chars)
        if "".join(chars) != word:
            break
    return "".join(chars)


class ScrambleGuessModal(discord.ui.Modal, title="Scramble Guess"):
    def __init__(self, game_id: int):
        super().__init__(custom_id=f"scram_modal:{game_id}")
        self.game_id = game_id
        self.answer = discord.ui.TextInput(label="Your guess", placeholder="type the word", required=True, max_length=32)
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            row = await conn.fetchrow(
                "SELECT word, scrambled, finished FROM games_scramble WHERE game_id=$1",
                self.game_id,
            )
        if not row:
            await interaction.response.send_message("Game not found.", ephemeral=True)
            return
        word, scrambled, finished = str(row[0]), str(row[1]), bool(row[2])
        if finished:
            await interaction.response.send_message("This scramble has finished.", ephemeral=True)
            return
        if self.answer.value.strip().lower() == word.lower():
            # mark finished and update winner
            async with pool.acquire() as conn:  # type: ignore
                await conn.execute(
                    "UPDATE games_scramble SET finished=TRUE, winner_id=$1 WHERE game_id=$2",
                    interaction.user.id,
                    self.game_id,
                )
                mrow = await conn.fetchrow("SELECT message_id FROM games_scramble WHERE game_id=$1", self.game_id)
            desc = f"`{scrambled}` → **{word}**\nWinner: <@{interaction.user.id}>"
            embed = discord.Embed(title="Scramble — Solved!", description=desc, color=discord.Color.green())
            embed.set_footer(text=FOOTER_TEXT)
            view = ScrambleView(self.game_id)
            for c in view.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("Incorrect. Try again!", ephemeral=True)


class ScrambleView(discord.ui.View):
    def __init__(self, game_id: int, reveal_enabled: bool = False):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.add_item(ScrambleGuessButton(game_id))
        self.add_item(ScrambleRevealButton(game_id, enabled=reveal_enabled))


class ScrambleGuessButton(discord.ui.Button):
    def __init__(self, game_id: int):
        super().__init__(label="Guess", style=discord.ButtonStyle.primary, custom_id=f"scram_btn:{game_id}")
        self.game_id = game_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ScrambleGuessModal(self.game_id))


class ScrambleRevealButton(discord.ui.Button):
    def __init__(self, game_id: int, enabled: bool = False):
        super().__init__(label="Reveal", style=discord.ButtonStyle.secondary, custom_id=f"scram_reveal:{game_id}")
        self.game_id = game_id
        self.disabled = not enabled

    async def callback(self, interaction: discord.Interaction):
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            row = await conn.fetchrow("SELECT word, scrambled, finished FROM games_scramble WHERE game_id=$1", self.game_id)
        if not row:
            await interaction.response.send_message("Game not found.", ephemeral=True)
            return
        word, scrambled, finished = str(row[0]), str(row[1]), bool(row[2])
        if finished:
            await interaction.response.send_message("This scramble has finished.", ephemeral=True)
            return
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_scramble SET finished=TRUE WHERE game_id=$1", self.game_id)
        desc = f"`{scrambled}` → **{word}**\nRevealed by a timeout."
        embed = discord.Embed(title="Scramble — Revealed", description=desc, color=discord.Color.orange())
        embed.set_footer(text=FOOTER_TEXT)
        view = ScrambleView(self.game_id)
        for c in view.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await interaction.response.edit_message(embed=embed, view=view)


class ScrambleCog(commands.Cog):
    """Word scramble mini-game (persistent)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="scramble", description="Start a word scramble puzzle in this channel")
    @app_commands.guild_only()
    async def scramble(self, interaction: discord.Interaction):
        word = random.choice(WORDS)
        scrambled = scramble_word(word)
        pool = getattr(self.bot, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_scramble (guild_id, channel_id, message_id, word, scrambled, finished) VALUES ($1,$2,$3,$4,$5,$6) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                word,
                scrambled,
                False,
            )
            game_id = int(rec[0])

        # 2-minute countdown
        total_secs = 120
        desc = f"Unscramble this word: `{scrambled}`\nLength: {len(word)}\nTime left: {total_secs}s"
        embed = discord.Embed(title="Word Scramble", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        view = ScrambleView(game_id, reveal_enabled=False)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_scramble SET message_id=$1 WHERE game_id=$2", msg.id, game_id)
        # Enable reveal after 30s and update countdown periodically; auto-close at 0
        async def countdown_task():
            nonlocal total_secs
            try:
                while total_secs > 0:
                    await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
                    total_secs = max(0, total_secs - 5)
                    # Check if finished
                    async with pool.acquire() as conn:  # type: ignore
                        row = await conn.fetchrow("SELECT word, scrambled, finished FROM games_scramble WHERE game_id=$1", game_id)
                    if not row:
                        return
                    word2, scr2, finished = str(row[0]), str(row[1]), bool(row[2])
                    if finished:
                        return
                    # Enable reveal at 30s
                    rev_enabled = total_secs <= 90
                    v2 = ScrambleView(game_id, reveal_enabled=rev_enabled)
                    new_desc = f"Unscramble this word: `{scr2}`\nLength: {len(word2)}\nTime left: {total_secs}s"
                    e2 = discord.Embed(title="Word Scramble", description=new_desc, color=BRAND_COLOR)
                    e2.set_footer(text=FOOTER_TEXT)
                    try:
                        await msg.edit(embed=e2, view=v2)
                    except Exception:
                        pass
                # Auto reveal when time hits 0 if not finished
                async with pool.acquire() as conn:  # type: ignore
                    row = await conn.fetchrow("SELECT word, scrambled, finished FROM games_scramble WHERE game_id=$1", game_id)
                if row and not bool(row[2]):
                    wordf, scrf = str(row[0]), str(row[1])
                    async with pool.acquire() as conn:  # type: ignore
                        await conn.execute("UPDATE games_scramble SET finished=TRUE WHERE game_id=$1", game_id)
                    descf = f"`{scrf}` → **{wordf}**\nTime expired."
                    ef = discord.Embed(title="Scramble — Time's Up", description=descf, color=discord.Color.orange())
                    ef.set_footer(text=FOOTER_TEXT)
                    vdone = ScrambleView(game_id)
                    for c in vdone.children:
                        if isinstance(c, discord.ui.Button):
                            c.disabled = True
                    try:
                        await msg.edit(embed=ef, view=vdone)
                    except Exception:
                        pass
            except Exception:
                pass
        # Fire and forget
        try:
            interaction.client.loop.create_task(countdown_task())
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ScrambleCog(bot))
    # Restore unfinished scrambles
    pool = getattr(bot, "pool", None)
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT game_id, message_id FROM games_scramble WHERE finished=FALSE")
        for r in rows:
            gid = int(r[0]); mid = int(r[1])
            try:
                bot.add_view(ScrambleView(gid), message_id=mid)
            except Exception:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE games_scramble SET finished=TRUE WHERE game_id=$1", gid)
