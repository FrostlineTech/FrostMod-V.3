#this is the file meant for logging voice join events 
#ensure this cog and command is loaded in the main file frostmodv3.py   
#ensure all embeds say powered by FSLLC / FrostlineSolutions.com at the bottom of the embed in the footer
#when admin uses /logs ensure they can toggle this on and off for the server to follow current flow
#review everything to ensure you stay consistent with the rest of the code 

import discord
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class VoiceJoinLogger(commands.Cog):
    """Logs when members join voice channels, controlled by /logs settings."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track voice session start times to compute durations on leave
        if not hasattr(bot, "voice_session_starts"):
            bot.voice_session_starts = {}  # type: ignore[var-annotated]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        # Only act on joins (before.channel is None and after.channel is not None)
        if member.bot or member.guild is None:
            return
        # Only fresh joins (no channel -> some channel)
        if before.channel is None and after.channel is not None:
            joined_channel = after.channel
        else:
            return

        pool = getattr(self.bot, "pool", None)
        if not pool:
            return
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_voice_join FROM general_server WHERE guild_id = $1",
                member.guild.id,
            )
            if not row or not row["log_voice_join"] or not row["logs_channel_id"]:
                return
            logs_channel_id = row["logs_channel_id"]

            # Update activity: increment voice_joins and set session start
            await conn.execute(
                """
                INSERT INTO user_activity (guild_id, user_id, voice_joins, last_seen, last_voice_channel_id)
                VALUES ($1, $2, 1, NOW(), $3)
                ON CONFLICT (guild_id, user_id) DO UPDATE
                SET voice_joins = user_activity.voice_joins + 1,
                    last_seen = NOW(),
                    last_voice_channel_id = EXCLUDED.last_voice_channel_id
                """,
                member.guild.id,
                member.id,
                getattr(joined_channel, "id", None),
            )

            # Update daily aggregate for voice joins
            await conn.execute(
                """
                INSERT INTO user_activity_daily (guild_id, user_id, day, voice_joins)
                VALUES ($1, $2, CURRENT_DATE, 1)
                ON CONFLICT (guild_id, user_id, day) DO UPDATE
                SET voice_joins = user_activity_daily.voice_joins + 1
                """,
                member.guild.id,
                member.id,
            )

        # Store session start in memory
        key = (member.guild.id, member.id)
        self.bot.voice_session_starts[key] = discord.utils.utcnow()  # type: ignore[attr-defined]

        # Send log embed
        channel = member.guild.get_channel(logs_channel_id) or await self.bot.fetch_channel(logs_channel_id)  # type: ignore[arg-type]
        if channel is None:
            return
        embed = discord.Embed(title="Voice Join", color=BRAND_COLOR)
        embed.add_field(name="User", value=f"{member.mention} ({member})", inline=False)
        embed.add_field(name="Channel", value=joined_channel.mention, inline=True)
        embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
        embed.set_footer(text=FOOTER_TEXT)
        try:
            await channel.send(embed=embed)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceJoinLogger(bot))