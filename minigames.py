from __future__ import annotations

import random
from typing import Optional

import discord
from discord import app_commands
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


# -------------------------- Connect4 --------------------------

class C4View(discord.ui.View):
    COLS = 7
    ROWS = 6

    def __init__(self, p1: int, p2: int):
        super().__init__(timeout=600)
        self.p1, self.p2 = p1, p2
        self.turn = p1
        self.grid = [[" "] * self.COLS for _ in range(self.ROWS)]  # bottom row is index ROWS-1
        self.winner: Optional[int] = None
        for col in range(self.COLS):
            self.add_item(C4Button(col))

    def drop(self, col: int, user_id: int) -> str:
        if self.winner or user_id != self.turn:
            return "invalid"
        # Find lowest empty slot
        row = None
        for r in range(self.ROWS - 1, -1, -1):
            if self.grid[r][col] == " ":
                row = r
                break
        if row is None:
            return "full"
        piece = "X" if self.turn == self.p1 else "O"
        self.grid[row][col] = piece
        if check_c4_win(self.grid):
            self.winner = user_id
        elif all(self.grid[0][c] != " " for c in range(self.COLS)):
            self.winner = 0
        else:
            self.turn = self.p2 if self.turn == self.p1 else self.p1
        return "ok"

    def render_embed(self) -> discord.Embed:
        # Render grid with simple characters
        lines = ["|".join(self.grid[r]) for r in range(self.ROWS)]
        desc = "```\n" + "\n".join(lines) + "\n```\n" + "Buttons drop in a column. X goes first."
        embed = discord.Embed(title="Connect 4", description=desc, color=BRAND_COLOR)
        if self.winner is None:
            embed.add_field(name="Turn", value=f"<@{self.turn}>", inline=False)
        elif self.winner == 0:
            embed.add_field(name="Result", value="It's a draw!", inline=False)
        else:
            embed.add_field(name="Winner", value=f"<@{self.winner}>", inline=False)
        embed.set_footer(text=FOOTER_TEXT)
        return embed


class C4Button(discord.ui.Button):
    def __init__(self, col: int):
        super().__init__(label=str(col + 1), style=discord.ButtonStyle.primary)
        self.col = col

    async def callback(self, interaction: discord.Interaction):
        view: C4View = self.view  # type: ignore
        res = view.drop(self.col, interaction.user.id)
        if res == "invalid":
            await interaction.response.send_message("Not your turn.", ephemeral=True)
            return
        if res == "full":
            await interaction.response.send_message("That column is full.", ephemeral=True)
            return
        if view.winner is not None:
            for c in view.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
        await interaction.response.edit_message(embed=view.render_embed(), view=view)


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
    async def rps(self, interaction: discord.Interaction):
        view = RPSView()
        embed = discord.Embed(title="Rock • Paper • Scissors", description="Pick one!", color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="tictactoe", description="Start TicTacToe vs another member")
    @app_commands.describe(opponent="The member to challenge")
    @app_commands.guild_only()
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
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            await interaction.response.send_message("Please challenge a human member.", ephemeral=True)
            return
        p1, p2 = interaction.user.id, opponent.id
        view = C4View(p1, p2)
        embed = view.render_embed()
        await interaction.response.send_message(content=f"<@{p1}> vs <@{p2}>", embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(MiniGamesCog(bot))
