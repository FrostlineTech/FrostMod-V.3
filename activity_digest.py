from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from branding import BRAND_COLOR, FOOTER_TEXT
from ui import make_embed


class ActivityDigest(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log = getattr(bot, "log", logging.getLogger(__name__))
        self.weekly_digest.start()

    def cog_unload(self):
        self.weekly_digest.cancel()

    @tasks.loop(hours=24)
    async def weekly_digest(self):
        now = datetime.now(timezone.utc)
        # Run on Sundays at 12:00 UTC
        if now.weekday() != 6 or now.hour < 12 or now.hour >= 13:
            return
        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT guild_id, digest_channel_id FROM general_server WHERE digest_channel_id IS NOT NULL")
            for row in rows:
                guild_id = row["guild_id"]
                channel_id = row["digest_channel_id"]
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                ch = guild.get_channel(int(channel_id))
                if not isinstance(ch, discord.TextChannel):
                    continue
                week_ago = (now - timedelta(days=7)).date()
                # Aggregate last week from daily rollups
                stats = await conn.fetch("""
                    SELECT SUM(messages) AS messages, SUM(voice_joins) AS voice_joins, SUM(voice_seconds) AS voice_seconds
                    FROM user_activity_daily WHERE guild_id=$1 AND day >= $2
                """, guild.id, week_ago)
                messages = stats[0]["messages"] or 0
                voice_joins = stats[0]["voice_joins"] or 0
                voice_seconds = stats[0]["voice_seconds"] or 0
                hours = round((voice_seconds or 0) / 3600, 1)

                embed = make_embed(
                    title=f"Weekly Activity — {guild.name}",
                    description=f"Messages: {messages}\nVoice joins: {voice_joins}\nVoice time: {hours}h",
                )
                try:
                    await ch.send(embed=embed)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityDigest(bot))
