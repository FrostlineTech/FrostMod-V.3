from __future__ import annotations

import random
from typing import Optional, List

import discord
from discord import app_commands
from discord.app_commands import checks
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class TriviaView(discord.ui.View):
    def __init__(self, qid: int, options: List[str], correct_idx: int):
        super().__init__(timeout=60)
        self.qid = qid
        self.correct_idx = correct_idx
        for i, text in enumerate(options):
            self.add_item(TriviaOptionButton(i, text, correct_idx))

    async def on_timeout(self) -> None:
        for c in self.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True


class TriviaOptionButton(discord.ui.Button):
    def __init__(self, idx: int, label_text: str, correct_idx: int):
        super().__init__(label=label_text, style=discord.ButtonStyle.primary)
        self.idx = idx
        self.correct_idx = correct_idx

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        correct = self.idx == self.correct_idx
        # Disable all buttons after first answer per user interaction
        for c in self.view.children:  # type: ignore
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        # Update score if correct
        if correct and interaction.guild_id is not None:
            pool = getattr(interaction.client, "pool", None)
            if pool is not None:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO trivia_scores (guild_id, user_id, score) VALUES ($1,$2,1) "
                        "ON CONFLICT (guild_id, user_id) DO UPDATE SET score = trivia_scores.score + 1",
                        interaction.guild_id,
                        user.id,
                    )
        # Respond with result
        verdict = "Correct!" if correct else "Incorrect"
        color = discord.Color.green() if correct else discord.Color.red()
        embed = discord.Embed(title=verdict, color=color)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.edit_message(embed=embed, view=self.view)


class TriviaCog(commands.Cog):
    """Guild trivia with local questions and leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trivia_add", description="Add a trivia question (4 options; specify the correct index 1-4)")
    @app_commands.describe(question="Question text", option1="Option 1", option2="Option 2", option3="Option 3", option4="Option 4", correct_index="1-4 index of the correct option", global_question="If true, question is global (usable in any guild)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def trivia_add(self, interaction: discord.Interaction, question: str, option1: str, option2: str, option3: str, option4: str, correct_index: int, global_question: Optional[bool] = False):
        if correct_index not in (1, 2, 3, 4):
            await interaction.response.send_message("correct_index must be 1-4", ephemeral=True)
            return
        options = [option1, option2, option3, option4]
        gid = None if global_question else interaction.guild_id
        pool = getattr(self.bot, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            await conn.execute(
                "INSERT INTO trivia_questions (guild_id, question, options, correct_idx, author_id) VALUES ($1,$2,$3,$4,$5)",
                gid,
                question,
                options,
                correct_index - 1,
                interaction.user.id,
            )
        await interaction.response.send_message("Question added.", ephemeral=True)

    @app_commands.command(name="trivia", description="Start a trivia question from local or global pool")
    @checks.cooldown(1, 5.0)
    async def trivia(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            rows = await conn.fetch(
                "SELECT id, question, options, correct_idx FROM trivia_questions WHERE guild_id=$1 OR guild_id IS NULL ORDER BY random() LIMIT 1",
                interaction.guild_id,
            )
        if not rows:
            await interaction.response.send_message("No trivia questions yet. Use /trivia_add to add some.", ephemeral=True)
            return
        rid, qtext, options, correct_idx = int(rows[0][0]), str(rows[0][1]), list(rows[0][2]), int(rows[0][3])
        view = TriviaView(rid, options, correct_idx)
        embed = discord.Embed(title="Trivia", description=qtext, color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="trivia_leaderboard", description="Show the guild trivia leaderboard")
    @app_commands.guild_only()
    async def trivia_leaderboard(self, interaction: discord.Interaction):
        pool = getattr(self.bot, "pool", None)
        async with pool.acquire() as conn:  # type: ignore
            rows = await conn.fetch(
                "SELECT user_id, score FROM trivia_scores WHERE guild_id=$1 ORDER BY score DESC LIMIT 10",
                interaction.guild_id,
            )
        if not rows:
            await interaction.response.send_message("No scores yet.", ephemeral=True)
            return
        lines = [f"<@{int(r[0])}> — {int(r[1])} pts" for r in rows]
        embed = discord.Embed(title="Trivia Leaderboard", description="\n".join(lines), color=BRAND_COLOR)
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TriviaCog(bot))
