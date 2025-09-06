from __future__ import annotations

import string
import random
from typing import Optional, List
import json
import datetime
import time

import discord
from discord import app_commands
from discord.app_commands import checks
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT

DEFAULT_WORDS = [
    "python", "discord", "frostmod", "hangman", "database", "asyncio", "embed",
    "moderation", "channel", "message", "heartbeat", "support"
]


def render_hangman(word: str, guessed: List[str]) -> str:
    display = " ".join([c if c in guessed or not c.isalpha() else "_" for c in word])
    wrong = sorted([g for g in guessed if g not in word])
    return display, ", ".join(wrong) if wrong else "(none)"


class HangmanView(discord.ui.View):
    def __init__(self, game_id: int, guessed: Optional[List[str]] = None):
        super().__init__(timeout=None)  # persistent
        self.game_id = game_id
        gset = set((guessed or []))
        # Two selects to cover A-Z (<=25 options per select), exclude already-guessed letters
        letters_am = [c for c in string.ascii_uppercase[:13] if c.lower() not in gset]
        letters_nz = [c for c in string.ascii_uppercase[13:] if c.lower() not in gset]
        if letters_am:
            self.add_item(HangmanSelect(game_id, "A-M", letters_am))
        if letters_nz:
            self.add_item(HangmanSelect(game_id, "N-Z", letters_nz))

    @staticmethod
    async def load_state(client: discord.Client, game_id: int):
        pool = getattr(client, "pool", None)
        if pool is None:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT guild_id, channel_id, message_id, starter_id, word, guessed, attempts_left, finished, winner_id "
                "FROM games_hangman WHERE game_id=$1",
                game_id,
            )
        return row

    @staticmethod
    async def save_state(client: discord.Client, game_id: int, *, guessed: List[str], attempts_left: int, finished: bool, winner_id: Optional[int]):
        pool = getattr(client, "pool", None)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE games_hangman SET guessed=$1::jsonb, attempts_left=$2, finished=$3, winner_id=$4 WHERE game_id=$5",
                json.dumps(guessed),
                attempts_left,
                finished,
                winner_id,
                game_id,
            )


class HangmanSelect(discord.ui.Select):
    def __init__(self, game_id: int, label: str, letters: list[str]):
        options = [discord.SelectOption(label=l, value=l) for l in letters]
        super().__init__(placeholder=label, options=options, min_values=1, max_values=1, custom_id=f"hang_sel:{game_id}:{label}")
        self.game_id = game_id
        self._last_by_user: dict[int, float] = {}

    async def callback(self, interaction: discord.Interaction):
        # Simple 2s per-user cooldown
        now = time.monotonic()
        last = self._last_by_user.get(interaction.user.id, 0.0)
        if now - last < 2.0:
            await interaction.response.send_message("You're pressing too fast. Please wait a moment.", ephemeral=True)
            return
        self._last_by_user[interaction.user.id] = now
        letter = self.values[0].lower()
        game_id = self.game_id
        row = await HangmanView.load_state(interaction.client, game_id)
        if row is None:
            await interaction.response.send_message("Game not found.", ephemeral=True)
            return
        word = str(row[4])
        raw_guessed = row[5]
        if isinstance(raw_guessed, list):
            guessed: List[str] = list(raw_guessed)
        else:
            try:
                guessed = list(json.loads(str(raw_guessed)))
            except Exception:
                guessed = []
        attempts_left = int(row[6])
        finished = bool(row[7])
        winner_id = row[8]

        if finished:
            await interaction.response.send_message("This game has finished.", ephemeral=True)
            return
        if letter in guessed:
            await interaction.response.send_message("Already guessed.", ephemeral=True)
            return

        guessed.append(letter)
        if letter not in word:
            attempts_left -= 1

        # Check win/lose
        all_revealed = all((not c.isalpha()) or (c in guessed) for c in word)
        if all_revealed:
            finished = True
            winner_id = interaction.user.id
        elif attempts_left <= 0:
            finished = True

        await HangmanView.save_state(interaction.client, game_id, guessed=guessed, attempts_left=attempts_left, finished=finished, winner_id=winner_id)

        # Build embed
        disp, wrong = render_hangman(word, guessed)
        desc = f"Word: {disp}\nWrong: {wrong}\nAttempts left: {attempts_left}"
        embed = discord.Embed(title="Hangman", description=desc, color=BRAND_COLOR)
        if finished:
            if attempts_left > 0:
                embed.add_field(name="Winner", value=f"<@{winner_id}>")
            else:
                embed.add_field(name="Result", value=f"You lost! The word was `{word}`")
        embed.set_footer(text=FOOTER_TEXT)

        view = HangmanView(game_id, guessed=guessed)
        if finished:
            for c in view.children:
                if isinstance(c, (discord.ui.Button, discord.ui.Select)):
                    c.disabled = True
        await interaction.response.edit_message(embed=embed, view=view)


class HangmanCog(commands.Cog):
    """Persistent Hangman game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="hangman", description="Start a Hangman game. Optionally provide a word; otherwise random.")
    @app_commands.describe(word="Optional custom word (letters and spaces only).")
    @app_commands.guild_only()
    @checks.cooldown(1, 10.0)
    async def hangman(self, interaction: discord.Interaction, word: Optional[str] = None):
        # sanitize
        if word is None:
            word = random.choice(DEFAULT_WORDS)
        word = "".join([c.lower() if (c.isalpha() or c == " ") else "" for c in word])
        if not word.strip():
            await interaction.response.send_message("Invalid word.", ephemeral=True)
            return

        pool = getattr(self.bot, "pool", None)
        guessed: List[str] = []
        attempts_left = 6
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_hangman (guild_id, channel_id, message_id, starter_id, word, guessed, attempts_left, finished) "
                "VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                interaction.user.id,
                word,
                json.dumps(guessed),
                attempts_left,
                False,
            )
            game_id = int(rec[0])

        view = HangmanView(game_id, guessed=guessed)
        disp, wrong = render_hangman(word, guessed)
        # Hearts visualization (total 6 lives)
        hearts = "❤️" * attempts_left + "🤍" * (6 - attempts_left)
        desc = f"Word: {disp}\nWrong: {wrong}\nLives: {hearts}"
        embed = discord.Embed(title="Hangman", description=desc, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_hangman SET message_id=$1 WHERE game_id=$2", msg.id, game_id)

        # Start a 2-minute countdown with auto-close
        total_secs = 120
        async def countdown_task():
            nonlocal total_secs
            try:
                while total_secs > 0:
                    await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
                    total_secs = max(0, total_secs - 5)
                    # Fetch state
                    row2 = await HangmanView.load_state(self.bot, game_id)  # type: ignore
                    if row2 is None:
                        return
                    word2 = str(row2[4])
                    raw_guessed2 = row2[5]
                    if isinstance(raw_guessed2, list):
                        guessed2: List[str] = list(raw_guessed2)
                    else:
                        try:
                            guessed2 = list(json.loads(str(raw_guessed2)))
                        except Exception:
                            guessed2 = []
                    attempts_left2 = int(row2[6])
                    finished2 = bool(row2[7])
                    if finished2 or attempts_left2 <= 0:
                        return
                    disp2, wrong2 = render_hangman(word2, guessed2)
                    hearts2 = "❤️" * attempts_left2 + "🤍" * (6 - attempts_left2)
                    desc2 = f"Word: {disp2}\nWrong: {wrong2}\nLives: {hearts2}\nTime left: {total_secs}s"
                    v2 = HangmanView(game_id, guessed=guessed2)
                    e2 = discord.Embed(title="Hangman", description=desc2, color=BRAND_COLOR)
                    e2.set_footer(text=FOOTER_TEXT)
                    try:
                        await msg.edit(embed=e2, view=v2)
                    except Exception:
                        pass
                # Time up; end the game if not already finished
                row3 = await HangmanView.load_state(self.bot, game_id)  # type: ignore
                if row3 is None:
                    return
                word3 = str(row3[4])
                attempts_left3 = int(row3[6])
                finished3 = bool(row3[7])
                if not finished3:
                    await HangmanView.save_state(self.bot, game_id, guessed=[], attempts_left=attempts_left3, finished=True, winner_id=None)  # type: ignore
                    vdone = HangmanView(game_id, guessed=[])
                    for c in vdone.children:
                        if isinstance(c, (discord.ui.Button, discord.ui.Select)):
                            c.disabled = True
                    ef = discord.Embed(title="Hangman — Time's Up", description=f"You ran out of time. The word was `{word3}`", color=discord.Color.orange())
                    ef.set_footer(text=FOOTER_TEXT)
                    try:
                        await msg.edit(embed=ef, view=vdone)
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            self.bot.loop.create_task(countdown_task())
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(HangmanCog(bot))
    # Restore unfinished games
    pool = getattr(bot, "pool", None)
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT game_id, message_id FROM games_hangman WHERE finished=FALSE")
        for r in rows:
            gid = int(r[0]); mid = int(r[1])
            try:
                bot.add_view(HangmanView(gid), message_id=mid)
            except Exception:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE games_hangman SET finished=TRUE WHERE game_id=$1", gid)
