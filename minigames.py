from __future__ import annotations

import random
from typing import Optional
import json

import discord
from discord import app_commands
from discord.app_commands import checks
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class RPSView(discord.ui.View):
    CHOICES = ["Rock", "Paper", "Scissors"]

    def __init__(self):
        super().__init__(timeout=30)
        for label in self.CHOICES:
            self.add_item(RPSButton(label))

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True


class RPSButton(discord.ui.Button):
    def __init__(self, choice_label: str):
        super().__init__(label=choice_label, style=discord.ButtonStyle.primary)
        self.choice_label = choice_label

    async def callback(self, interaction: discord.Interaction):
        user_choice = self.choice_label
        bot_choice = random.choice(RPSView.CHOICES)
        outcome = result_rps(user_choice, bot_choice)
        embed = discord.Embed(title="Rock • Paper • Scissors", color=BRAND_COLOR)
        embed.add_field(name="You", value=user_choice)
        embed.add_field(name="Bot", value=bot_choice)
        embed.add_field(name="Result", value=outcome, inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.edit_message(embed=embed, view=None)


def result_rps(user: str, bot: str) -> str:
    if user == bot:
        return "Tie"
    wins = {"Rock": "Scissors", "Paper": "Rock", "Scissors": "Paper"}
    return "You Win" if wins[user] == bot else "You Lose"


# -------------------------- TicTacToe --------------------------

class TTTView(discord.ui.View):
    def __init__(self, p1: int, p2: int):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.turn = p1
        self.board = [" "] * 9
        self.winner: Optional[int] = None
        # Create 3x3 buttons
        for i in range(9):
            self.add_item(TTTButton(i))

    def mark(self, index: int, user_id: int) -> str:
        if self.winner or self.board[index] != " " or user_id != self.turn:
            return "invalid"
        symbol = "X" if self.turn == self.p1 else "O"
        self.board[index] = symbol
        if check_ttt_win(self.board):
            self.winner = user_id
        elif all(c != " " for c in self.board):
            self.winner = 0  # draw
        else:
            self.turn = self.p2 if self.turn == self.p1 else self.p1
        return "ok"

    def render_embed(self) -> discord.Embed:
        rows = [" | ".join(self.board[i:i+3]) for i in range(0, 9, 3)]
        grid = "\n---------\n".join(rows)
        title = "Tic Tac Toe"
        desc = f"```\n{grid}\n```"
        embed = discord.Embed(title=title, description=desc, color=BRAND_COLOR)
        if self.winner is None:
            embed.add_field(name="Turn", value=f"<@{self.turn}>", inline=False)
        elif self.winner == 0:
            embed.add_field(name="Result", value="It's a draw!", inline=False)
        else:
            embed.add_field(name="Winner", value=f"<@{self.winner}>", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        return embed


class TTTButton(discord.ui.Button):
    def __init__(self, index: int):
        row = index // 3
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=row)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: TTTView = self.view  # type: ignore
        status = view.mark(self.index, interaction.user.id)
        if status == "invalid":
            await interaction.response.send_message("Not your turn or cell occupied.", ephemeral=True)
            return
        # Update this button label
        self.label = view.board[self.index]
        if view.winner is not None:
            for c in view.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
        await interaction.response.edit_message(embed=view.render_embed(), view=view)


def check_ttt_win(b: list[str]) -> bool:
    wins = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
        (0, 4, 8), (2, 4, 6)              # diags
    ]
    for a, c, d in wins:
        if b[a] != " " and b[a] == b[c] == b[d]:
            return True
    return False


# -------------------------- Connect4 (Persistent) --------------------------

async def _avatar_url(guild: Optional[discord.Guild], user_id: Optional[int]) -> Optional[str]:
    if guild is None or user_id is None:
        return None
    m = guild.get_member(user_id)
    if m is None:
        try:
            m = await guild.fetch_member(user_id)
        except Exception:
            return None
    try:
        return m.display_avatar.url
    except Exception:
        return None


def _c4_embed_from_state(grid: list[list[str]], turn: Optional[int], winner: Optional[int], thumb_url: Optional[str] = None) -> discord.Embed:
    rows = len(grid)
    lines = ["|".join(grid[r]) for r in range(rows)]
    desc = "```\n" + "\n".join(lines) + "\n```\n" + "Buttons drop in a column. X goes first."
    embed = discord.Embed(title="Connect 4", description=desc, color=BRAND_COLOR)
    if winner is None and turn is not None:
        embed.add_field(name="Turn", value=f"<@{turn}>", inline=False)
    elif winner == 0:
        embed.add_field(name="Result", value="It's a draw!", inline=False)
    elif winner is not None:
        embed.add_field(name="Winner", value=f"<@{winner}>", inline=False)
    if thumb_url:
        try:
            embed.set_thumbnail(url=thumb_url)
        except Exception:
            pass
    embed.set_footer(text=FOOTER_TEXT)
    return embed


class C4PersistentView(discord.ui.View):
    COLS = 7
    ROWS = 6

    def __init__(self, game_id: int, finished: bool = False, p1: Optional[int] = None, p2: Optional[int] = None):
        super().__init__(timeout=None)  # persistent
        self.game_id = game_id
        for col in range(self.COLS):
            cid = f"c4:{game_id}:{col}"
            self.add_item(C4PersistentButton(col, cid))
        if finished and p1 and p2:
            self.add_item(C4RematchButton(game_id, p1, p2))

    @staticmethod
    async def load_state(interaction: discord.Interaction, game_id: int):
        pool = getattr(interaction.client, "pool", None)
        if pool is None:
            return None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT guild_id, channel_id, message_id, p1, p2, turn, winner, grid, finished FROM games_connect4 WHERE game_id=$1",
                game_id,
            )
        return row

    @staticmethod
    async def save_state(interaction: discord.Interaction, game_id: int, *, grid, turn, winner, finished: bool):
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE games_connect4 SET grid=$1::jsonb, turn=$2, winner=$3, finished=$4 WHERE game_id=$5",
                json.dumps(grid),
                turn,
                winner,
                finished,
                game_id,
            )


class C4PersistentButton(discord.ui.Button):
    def __init__(self, col: int, custom_id: str):
        super().__init__(label=str(col + 1), style=discord.ButtonStyle.primary, custom_id=custom_id)
        self.col = col

    async def callback(self, interaction: discord.Interaction):
        # Parse game_id from custom_id: c4:{game_id}:{col}
        try:
            _, game_id_str, _ = self.custom_id.split(":")  # type: ignore
            game_id = int(game_id_str)
        except Exception:
            await interaction.response.send_message("Invalid game identifier.", ephemeral=True)
            return

        row = await C4PersistentView.load_state(interaction, game_id)
        if row is None:
            await interaction.response.send_message("Game could not be loaded.", ephemeral=True)
            return
        if row[8]:  # finished
            await interaction.response.send_message("This game has finished.", ephemeral=True)
            return

        p1, p2 = int(row[3]), int(row[4])
        turn = int(row[5])
        winner = row[6]
        grid = row[7]
        if isinstance(grid, str):
            try:
                grid = json.loads(grid)
            except Exception:
                grid = [[" "] * C4PersistentView.COLS for _ in range(C4PersistentView.ROWS)]
        grid: list[list[str]]

        # Validate turn
        if interaction.user.id != turn:
            await interaction.response.send_message("Not your turn.", ephemeral=True)
            return

        # Drop logic
        row_idx = None
        for r in range(C4PersistentView.ROWS - 1, -1, -1):
            if grid[r][self.col] == " ":
                row_idx = r
                break
        if row_idx is None:
            await interaction.response.send_message("That column is full.", ephemeral=True)
            return

        piece = "X" if turn == p1 else "O"
        grid[row_idx][self.col] = piece

        # Determine next state
        if check_c4_win(grid):
            winner = interaction.user.id
            finished = True
            next_turn = None
        elif all(grid[0][c] != " " for c in range(C4PersistentView.COLS)):
            winner = 0
            finished = True
            next_turn = None
        else:
            next_turn = p2 if turn == p1 else p1
            finished = False

        # Persist
        await C4PersistentView.save_state(
            interaction,
            game_id,
            grid=grid,
            turn=next_turn if next_turn is not None else (turn),
            winner=winner,
            finished=finished,
        )

        # Edit message
        thumb = await _avatar_url(interaction.guild, next_turn if next_turn is not None else (turn))
        embed = _c4_embed_from_state(grid, next_turn, winner, thumb_url=thumb)
        # Keep buttons; disable visually when finished
        view = C4PersistentView(game_id, finished=finished, p1=p1, p2=p2)
        if finished:
            for c in view.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
        await interaction.response.edit_message(embed=embed, view=view)


class C4RematchButton(discord.ui.Button):
    def __init__(self, game_id: int, p1: int, p2: int):
        super().__init__(label="Rematch", style=discord.ButtonStyle.secondary, custom_id=f"c4_rematch:{game_id}")
        self.game_id = game_id
        self.p1 = p1
        self.p2 = p2

    async def callback(self, interaction: discord.Interaction):
        # Start a fresh game with same players (swap order so loser can start if desired)
        p1, p2 = self.p2, self.p1
        pool = getattr(interaction.client, "pool", None)
        grid = [[" "] * C4PersistentView.COLS for _ in range(C4PersistentView.ROWS)]
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_connect4 (guild_id, channel_id, message_id, p1, p2, turn, winner, grid, finished) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                p1,
                p2,
                p1,
                None,
                json.dumps(grid),
                False,
            )
            new_game_id = int(rec[0])
        thumb = await _avatar_url(interaction.guild, p1)
        embed = _c4_embed_from_state(grid, p1, None, thumb_url=thumb)
        view = C4PersistentView(new_game_id)
        await interaction.response.send_message(content=f"<@{p1}> vs <@{p2}>", embed=embed, view=view)
        msg = await interaction.original_response()
        pool = getattr(interaction.client, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute("UPDATE games_connect4 SET message_id=$1 WHERE game_id=$2", msg.id, new_game_id)


def check_c4_win(g: list[list[str]]) -> bool:
    R, C = len(g), len(g[0])
    def four(a, b, c, d):
        return a != " " and a == b == c == d
    for r in range(R):
        for c in range(C):
            if c + 3 < C and four(g[r][c], g[r][c+1], g[r][c+2], g[r][c+3]):
                return True
            if r + 3 < R and four(g[r][c], g[r+1][c], g[r+2][c], g[r+3][c]):
                return True
            if r + 3 < R and c + 3 < C and four(g[r][c], g[r+1][c+1], g[r+2][c+2], g[r+3][c+3]):
                return True
            if r - 3 >= 0 and c + 3 < C and four(g[r][c], g[r-1][c+1], g[r-2][c+2], g[r-3][c+3]):
                return True
    return False


class MiniGamesCog(commands.Cog):
    """Button-based mini games: TicTacToe, RPS, Connect4."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="rps", description="Play Rock-Paper-Scissors vs the bot (buttons)")
    @checks.cooldown(1, 5.0)
    async def rps(self, interaction: discord.Interaction):
        view = RPSView()
        embed = discord.Embed(title="Rock • Paper • Scissors", description="Pick one!", color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="tictactoe", description="Start TicTacToe vs another member")
    @app_commands.describe(opponent="The member to challenge")
    @app_commands.guild_only()
    @checks.cooldown(1, 10.0)
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("Please challenge a human member.", ephemeral=True)
            return
        p1, p2 = interaction.user.id, opponent.id
        view = TTTView(p1, p2)
        embed = view.render_embed()
        await interaction.response.send_message(content=f"<@{p1}> vs <@{p2}>", embed=embed, view=view)

    @app_commands.command(name="connect4", description="Start Connect 4 vs another member")
    @app_commands.describe(opponent="The member to challenge")
    @app_commands.guild_only()
    @checks.cooldown(1, 10.0)
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("Please challenge a human member.", ephemeral=True)
            return
        p1, p2 = interaction.user.id, opponent.id
        # Initialize DB row first
        pool = getattr(self.bot, "pool", None)
        grid = [[" "] * C4PersistentView.COLS for _ in range(C4PersistentView.ROWS)]
        async with pool.acquire() as conn:  # type: ignore
            rec = await conn.fetchrow(
                "INSERT INTO games_connect4 (guild_id, channel_id, message_id, p1, p2, turn, winner, grid, finished) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9) RETURNING game_id",
                interaction.guild_id,
                interaction.channel_id,
                0,
                p1,
                p2,
                p1,
                None,
                json.dumps(grid),
                False,
            )
            game_id = int(rec[0])

        view = C4PersistentView(game_id)
        thumb = await _avatar_url(interaction.guild, p1)
        embed = _c4_embed_from_state(grid, p1, None, thumb_url=thumb)
        await interaction.response.send_message(content=f"<@{p1}> vs <@{p2}>", embed=embed, view=view)
        # Update message_id in DB
        msg = await interaction.original_response()
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute(
                "UPDATE games_connect4 SET message_id=$1 WHERE game_id=$2",
                msg.id,
                game_id,
            )


async def setup(bot: commands.Bot):
    cog = MiniGamesCog(bot)
    await bot.add_cog(cog)
    # Restore unfinished Connect4 games
    pool = getattr(bot, "pool", None)
    if pool is not None:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT game_id, message_id FROM games_connect4 WHERE finished=FALSE")
        for r in rows:
            gid = int(r[0])
            mid = int(r[1])
            try:
                bot.add_view(C4PersistentView(gid), message_id=mid)
            except Exception:
                # If message no longer exists, mark finished to clean up
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE games_connect4 SET finished=TRUE WHERE game_id=$1", gid)
