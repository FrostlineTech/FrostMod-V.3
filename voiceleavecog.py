#this is the file meant for logging voice leave events 
#ensure this cog and command is loaded in the main file frostmodv3.py   
#ensure all embeds say powered by FSLLC / FrostlineSolutions.com at the bottom of the embed in the footer
#when admin uses /logs ensure they can toggle this on and off for the server to follow current flow
#review everything to ensure you stay consistent with the rest of the code 

import discord
from discord.ext import commands

from branding import BRAND_COLOR, FOOTER_TEXT


class VoiceLeaveLogger(commands.Cog):
    """Logs when members leave voice channels, controlled by /logs settings, and tracks durations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(bot, "voice_session_starts"):
            bot.voice_session_starts = {}  # type: ignore[var-annotated]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or member.guild is None:
            return
        # Only process true leaves (channel -> None). Ignore switches and state-only changes.
        left_channel = None
        if before.channel is not None and after.channel is None:
            left_channel = before.channel
        else:
            return

        pool = getattr(self.bot, "pool", None)
        if not pool:
            return

        logs_channel_id = None
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT logs_channel_id, log_voice_leave FROM general_server WHERE guild_id = $1",
                member.guild.id,
            )
            if not row or not row["log_voice_leave"] or not row["logs_channel_id"]:
                # Still update activity duration if tracked
                pass
            else:
                logs_channel_id = row["logs_channel_id"]

            # Compute and persist voice duration if we have a start time
            key = (member.guild.id, member.id)
            start = getattr(self.bot, "voice_session_starts", {}).get(key)
            seconds = 0
            if start is not None:
                now = discord.utils.utcnow()
                seconds = int((now - start).total_seconds())
                # Clear the session start for this user
                try:
                    del self.bot.voice_session_starts[key]
                except Exception:
                    pass
            if seconds > 0:
                await conn.execute(
                    """
                    INSERT INTO user_activity (guild_id, user_id, voice_seconds, last_seen, last_voice_channel_id)
                    VALUES ($1, $2, $3, NOW(), $4)
                    ON CONFLICT (guild_id, user_id) DO UPDATE
                    SET voice_seconds = user_activity.voice_seconds + EXCLUDED.voice_seconds,
                        last_seen = NOW(),
                        last_voice_channel_id = COALESCE(EXCLUDED.last_voice_channel_id, user_activity.last_voice_channel_id)
                    """,
                    member.guild.id,
                    member.id,
                    seconds,
                    getattr(left_channel, "id", None),
                )

                # Update daily aggregate for voice seconds
                await conn.execute(
                    """
                    INSERT INTO user_activity_daily (guild_id, user_id, day, voice_seconds)
                    VALUES ($1, $2, CURRENT_DATE, $3)
                    ON CONFLICT (guild_id, user_id, day) DO UPDATE
                    SET voice_seconds = user_activity_daily.voice_seconds + EXCLUDED.voice_seconds
                    """,
                    member.guild.id,
                    member.id,
                    seconds,
                )

        # Send embed if enabled
        if logs_channel_id:
            channel = member.guild.get_channel(logs_channel_id) or await self.bot.fetch_channel(logs_channel_id)  # type: ignore[arg-type]
            if channel is None:
                return
            embed = discord.Embed(title="Voice Leave", color=BRAND_COLOR)
            embed.add_field(name="User", value=f"{member} (ID: {member.id})", inline=False)
            if left_channel is not None:
                embed.add_field(name="Channel", value=left_channel.mention, inline=True)
            embed.add_field(name="Time", value=discord.utils.format_dt(discord.utils.utcnow(), style="F"), inline=True)
            embed.set_footer(text=FOOTER_TEXT)
            try:
                await channel.send(embed=embed)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceLeaveLogger(bot))