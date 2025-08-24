#the point of this file is to save and log the activity of a user in a server 
#ensure this cog and command is loaded in the main file frostmodv3.py   
#when user uses /activity User it will show the activity antalytics of a user in a server 
#ensure all users can use this command 
#save all activity metrics to database create a new table and give the sql in the file schema.sql 
#review everything to ensure you stay consistent with the rest of the code 

import discord
from discord import app_commands
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class ActivityCog(commands.Cog):
    """Tracks user activity and provides `/activity` to view metrics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Track message counts in guild text channels
        if message.author.bot or message.guild is None:
            return
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            # Update all-time counters and last text channel
            await conn.execute(
                """
                INSERT INTO user_activity (guild_id, user_id, messages_sent, last_seen, last_text_channel_id)
                VALUES ($1, $2, 1, NOW(), $3)
                ON CONFLICT (guild_id, user_id) DO UPDATE
                SET messages_sent = user_activity.messages_sent + 1,
                    last_seen = NOW(),
                    last_text_channel_id = EXCLUDED.last_text_channel_id
                """,
                message.guild.id,
                message.author.id,
                getattr(message.channel, "id", None),
            )

            # Update daily aggregate
            await conn.execute(
                """
                INSERT INTO user_activity_daily (guild_id, user_id, day, messages)
                VALUES ($1, $2, CURRENT_DATE, 1)
                ON CONFLICT (guild_id, user_id, day) DO UPDATE
                SET messages = user_activity_daily.messages + 1
                """,
                message.guild.id,
                message.author.id,
            )

    @app_commands.command(name="activity", description="Show a user's server activity")
    @app_commands.describe(user="User to view; defaults to you", period="Time period")
    @app_commands.choices(period=[
        app_commands.Choice(name="All Time", value="all"),
        app_commands.Choice(name="This Week", value="week"),
        app_commands.Choice(name="This Month", value="month"),
    ])
    async def activity(self, interaction: discord.Interaction, user: discord.User | None = None, period: app_commands.Choice[str] | None = None):
        # Allow all users, guild only
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        await interaction.response.defer()

        target = user or interaction.user
        pool = getattr(self.bot, "pool", None)
        messages = 0
        vjoins = 0
        vseconds = 0
        last_seen = None
        last_text_channel_id = None
        last_voice_channel_id = None
        rank_by_messages = None
        total_tracked = None
        period_key = (period.value if period else "all")
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT messages_sent, voice_joins, voice_seconds, last_seen, last_text_channel_id, last_voice_channel_id FROM user_activity WHERE guild_id = $1 AND user_id = $2",
                    interaction.guild.id,
                    target.id,
                )
                if row:
                    messages = row["messages_sent"] or 0
                    vjoins = row["voice_joins"] or 0
                    vseconds = row["voice_seconds"] or 0
                    last_seen = row["last_seen"]
                    last_text_channel_id = row["last_text_channel_id"]
                    last_voice_channel_id = row["last_voice_channel_id"]

                # If period is week/month, override counters with aggregated daily values
                if period_key in ("week", "month"):
                    days = 7 if period_key == "week" else 30
                    agg = await conn.fetchrow(
                        """
                        SELECT COALESCE(SUM(messages),0) AS m,
                               COALESCE(SUM(voice_joins),0) AS vj,
                               COALESCE(SUM(voice_seconds),0) AS vs
                        FROM user_activity_daily
                        WHERE guild_id = $1 AND user_id = $2 AND day >= CURRENT_DATE - ($3::INT - 1)
                        """,
                        interaction.guild.id,
                        target.id,
                        days,
                    )
                    if agg:
                        messages = int(agg["m"]) or 0
                        vjoins = int(agg["vj"]) or 0
                        vseconds = int(agg["vs"]) or 0

                    # Rank within period by messages
                    rank_row = await conn.fetchrow(
                        """
                        SELECT 1 + COUNT(*) AS rank
                        FROM (
                          SELECT user_id, SUM(messages) AS m
                          FROM user_activity_daily
                          WHERE guild_id = $1 AND day >= CURRENT_DATE - ($2::INT - 1)
                          GROUP BY user_id
                        ) t
                        WHERE t.m > $3
                        """,
                        interaction.guild.id,
                        days,
                        messages,
                    )
                    count_row = await conn.fetchrow(
                        """
                        SELECT COUNT(*) AS total FROM (
                          SELECT user_id
                          FROM user_activity_daily
                          WHERE guild_id = $1 AND day >= CURRENT_DATE - ($2::INT - 1)
                          GROUP BY user_id
                        ) t
                        """,
                        interaction.guild.id,
                        days,
                    )
                    if rank_row:
                        rank_by_messages = rank_row["rank"]
                    if count_row:
                        total_tracked = count_row["total"]
                else:
                    # All-time rank
                    rank_row = await conn.fetchrow(
                        "SELECT 1 + COUNT(*) AS rank FROM user_activity WHERE guild_id = $1 AND messages_sent > $2",
                        interaction.guild.id,
                        messages,
                    )
                    count_row = await conn.fetchrow(
                        "SELECT COUNT(*) AS total FROM user_activity WHERE guild_id = $1",
                        interaction.guild.id,
                    )
                    if rank_row:
                        rank_by_messages = rank_row["rank"]
                    if count_row:
                        total_tracked = count_row["total"]

        # Helpers
        def fmt_int(n: int) -> str:
            return f"{n:,}"

        # Voice time removed from UI (still tracked under the hood)

        # Resolve member for join date and roles if available
        member = interaction.guild.get_member(target.id)

        # Medal for rank
        def medal_for(rank: int | None) -> str:
            if not rank:
                return ""
            return "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "🏅"

        # Pluralization helpers
        def s(word: str, count: int) -> str:
            return word if count == 1 else word + "s"

        # Short, clean summary line with period and rank
        rank_part = ""
        if rank_by_messages and total_tracked:
            rank_part = f" {medal_for(rank_by_messages)} #{rank_by_messages}/{total_tracked}"
        period_label = "All Time" if period_key == "all" else ("This Week" if period_key == "week" else "This Month")
        summary = (
            f"**{fmt_int(messages)}** {s('msg', messages)} • "
            f"**{fmt_int(vjoins)}** {s('join', vjoins)}{rank_part}\n_({period_label})_"
        )

        embed = discord.Embed(color=BRAND_COLOR, description=summary)
        # Author with avatar
        try:
            embed.set_author(name=f"{getattr(member, 'display_name', target.name)}'s Activity", icon_url=target.display_avatar.url)
        except Exception:
            pass
        # Big thumbnail avatar
        try:
            embed.set_thumbnail(url=target.display_avatar.url)
        except Exception:
            pass

        # Core stats
        embed.add_field(name="💬 Messages", value=fmt_int(messages), inline=True)
        embed.add_field(name="🎙️ Voice Joins", value=fmt_int(vjoins), inline=True)

        # Member since and last seen (absolute + relative)
        if isinstance(member, discord.Member) and member.joined_at:
            abs_ = discord.utils.format_dt(member.joined_at, style="F")
            rel_ = discord.utils.format_dt(member.joined_at, style="R")
            embed.add_field(name="📅 Member Since", value=f"{abs_} ({rel_})", inline=False)
        if last_seen:
            abs_ls = discord.utils.format_dt(last_seen, style="F")
            rel_ls = discord.utils.format_dt(last_seen, style="R")
            embed.add_field(name="👀 Last Seen", value=f"{abs_ls} ({rel_ls})", inline=False)

        # Roles summary (top roles by position, excluding @everyone)
        if isinstance(member, discord.Member):
            roles = [r for r in member.roles if r.name != "@everyone"]
            roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)
            shown = roles_sorted[:3]
            remainder = max(0, len(roles_sorted) - len(shown))
            if shown:
                more = f" +{remainder} more" if remainder else ""
                value = ", ".join(r.mention for r in shown) + more
            else:
                value = "None"
            embed.add_field(name="🏷️ Roles", value=value, inline=False)

        # Progress bar for rank and percentile
        if rank_by_messages and total_tracked and total_tracked > 0:
            # Percentile-like score (higher is better for bar)
            percentile = int(round((1 - (rank_by_messages - 1) / total_tracked) * 100))
            percentile = max(0, min(100, percentile))
            # Top % (lower is better for placement)
            import math
            top_pct = int(math.ceil((rank_by_messages / total_tracked) * 100))
            # 10-segment bar based on percentile
            filled = max(0, min(10, int(round(percentile / 10))))
            bar = "█" * filled + "░" * (10 - filled)
            embed.add_field(name="🏆 Rank", value=f"{bar}  Top {top_pct}% (#{rank_by_messages}/{total_tracked})", inline=False)

        # Last channels if known
        lt = interaction.guild.get_channel(last_text_channel_id) if last_text_channel_id else None
        lv = interaction.guild.get_channel(last_voice_channel_id) if last_voice_channel_id else None
        last_parts = []
        if lt:
            last_parts.append(f"Last text: {lt.mention}")
        if lv:
            last_parts.append(f"Last voice: {lv.mention}")
        if last_parts:
            embed.add_field(name="📌 Recent Activity", value=" • ".join(last_parts), inline=False)

        # Subtle context in footer instead of a dedicated field
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityCog(bot))