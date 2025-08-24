"""
Main entry point for the bot.
Currently: minimal connect-only bot with presence.

Future plans (from notes):
- /welcome channel (channel)
- /leave channel (channel)
- /welcome message (message) {user} {guild} {membercount}
- /leave message (message) {user} {guild} {membercount}
- Ensure all embeds say powered by FSLLC / FrostlineSolutions.com in the footer
"""

import os
import sys

import logging
from time import perf_counter
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncpg


def main() -> None:
    # Load environment variables from .env
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    dev_guild_id_raw = os.getenv("Developer_Guild_ID")
    if not token:
        print("[ERROR] DISCORD_TOKEN not found in environment/.env.")
        sys.exit(1)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )

    # Intents
    intents = discord.Intents.default()
    intents.message_content = True  # Needed if you later read message content
    intents.members = True  # For member join/leave features later
    intents.voice_states = True  # For voice join/leave tracking
    intents.presences = True  # For activity tracking

    bot = commands.Bot(command_prefix="!", intents=intents)
    bot.log = logging.getLogger("frostmod")
    # Track start time for uptime in /status
    bot.start_time = discord.utils.utcnow()

    from branding import GREEN, YELLOW, RED, FOOTER_TEXT
    # Health and DB checks are now provided by extensions: statuscog (/status) and dbcheckcog (/db)

    async def setup_extensions():
        try:
            await bot.load_extension("purgecog")
            bot.log.info("[EXT] Loaded extension: purgecog")
        except Exception as e:
            bot.log.warning(f"Failed to load extension 'purgecog': {e}")
        for ext in ("Welcomecog", "Leavecog", "autorolecog", "help", "Webserver", "rules", "deletedmescog", "usrchangcog", "dbcheckcog", "statuscog", "serverinfocog",
                    "dadjokecog", "voicejoincog", "voiceleavecog", "Activtycog", "publicinfo", "polls", "utilityimages", "minigames", "memes"):
            try:
                await bot.load_extension(ext)
                bot.log.info(f"[EXT] Loaded extension: {ext}")
            except Exception as e:
                bot.log.warning(f"Failed to load extension '{ext}': {e}")

    async def init_db():
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5432"))

        if not all([db_name, db_user, db_password]):
            bot.log.warning("Database credentials missing; skipping DB init. Set DB_NAME, DB_USER, DB_PASSWORD in .env")
            bot.pool = None
            return

        # Pass parameters directly to avoid URL-encoding issues with special characters in passwords
        bot.log.info(f"[DB] Connecting to {db_host}:{db_port} db={db_name} user={db_user}")
        bot.pool = await asyncpg.create_pool(
            user=db_user,
            password=db_password,
            database=db_name,
            host=db_host,
            port=db_port,
            min_size=1,
            max_size=5,
        )
        bot.log.info("[DB] Connection pool established")

        create_sql = """
        BEGIN;
        -- Base tables
        CREATE TABLE IF NOT EXISTS general_server (
            guild_id BIGINT PRIMARY KEY,
            guild_name TEXT NOT NULL,
            join_role_id BIGINT,
            welcome_channel_id BIGINT,
            leave_channel_id BIGINT,
            welcome_message TEXT,
            leave_message TEXT,
            -- New logging settings (present for fresh installs)
            logs_channel_id BIGINT,
            log_message_delete BOOLEAN NOT NULL DEFAULT FALSE,
            log_nickname_change BOOLEAN NOT NULL DEFAULT FALSE,
            log_role_change BOOLEAN NOT NULL DEFAULT FALSE,
            log_avatar_change BOOLEAN NOT NULL DEFAULT FALSE,
            log_message_edit BOOLEAN NOT NULL DEFAULT FALSE,
            log_member_join BOOLEAN NOT NULL DEFAULT FALSE,
            log_member_leave BOOLEAN NOT NULL DEFAULT FALSE,
            log_voice_join BOOLEAN NOT NULL DEFAULT FALSE,
            log_voice_leave BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS user_joins (
            user_id BIGINT NOT NULL,
            user_name TEXT NOT NULL,
            guild_id BIGINT NOT NULL,
            guild_name TEXT NOT NULL,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS user_leaves (
            user_id BIGINT NOT NULL,
            user_name TEXT NOT NULL,
            guild_id BIGINT NOT NULL,
            guild_name TEXT NOT NULL,
            left_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_user_joins_guild_time ON user_joins (guild_id, joined_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_leaves_guild_time ON user_leaves (guild_id, left_at DESC);

        -- Idempotent migrations for existing installs
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS logs_channel_id BIGINT;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_message_delete BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_nickname_change BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_role_change BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_avatar_change BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_message_edit BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_member_join BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_member_leave BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_voice_join BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_voice_leave BOOLEAN NOT NULL DEFAULT FALSE;

        -- Activity tracking
        CREATE TABLE IF NOT EXISTS user_activity (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            messages_sent BIGINT NOT NULL DEFAULT 0,
            voice_joins BIGINT NOT NULL DEFAULT 0,
            voice_seconds BIGINT NOT NULL DEFAULT 0,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_text_channel_id BIGINT,
            last_voice_channel_id BIGINT,
            PRIMARY KEY (guild_id, user_id)
        );

        -- Daily rollups for activity (used by /activity period views and rankings)
        CREATE TABLE IF NOT EXISTS user_activity_daily (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            day DATE NOT NULL,
            messages BIGINT NOT NULL DEFAULT 0,
            voice_joins BIGINT NOT NULL DEFAULT 0,
            voice_seconds BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, day)
        );

        -- Idempotent migrations to ensure columns exist on older installs
        ALTER TABLE user_activity ADD COLUMN IF NOT EXISTS last_text_channel_id BIGINT;
        ALTER TABLE user_activity ADD COLUMN IF NOT EXISTS last_voice_channel_id BIGINT;
        COMMIT;
        """
        async with bot.pool.acquire() as conn:
            bot.log.info("[DB] Ensuring tables exist (idempotent)")
            await conn.execute(create_sql)
            bot.log.info("[DB] Tables ensured")

    @bot.event
    async def setup_hook():
        # Initialize DB first so cogs can use bot.pool
        await init_db()
        # Load cogs/extensions before the bot is ready so app commands exist for sync
        await setup_extensions()
        # Global sync first so commands are registered globally (may take time to propagate on Discord side)
        try:
            global_synced = await bot.tree.sync()
            bot.log.info(f"[SYNC] Globally synced {len(global_synced)} app command(s).")
        except Exception as e:
            bot.log.warning(f"Global sync failed: {e}")

        # Developer guild fast sync by copying globals to the guild and syncing
        if dev_guild_id_raw:
            try:
                dev_guild_id = int(dev_guild_id_raw)
                guild_obj = discord.Object(id=dev_guild_id)
                bot.tree.copy_global_to(guild=guild_obj)
                guild_synced = await bot.tree.sync(guild=guild_obj)
                bot.log.info(f"[SYNC] Synced {len(guild_synced)} app command(s) to developer guild {dev_guild_id}.")
            except ValueError:
                bot.log.warning(f"Invalid Developer_Guild_ID value: {dev_guild_id_raw}")
            except Exception as e:
                bot.log.warning(f"Developer guild sync failed: {e}")

    @bot.event
    async def on_ready():
        # Set activity status
        activity = discord.Game(name="Keeping the community safe 24/7")
        await bot.change_presence(status=discord.Status.online, activity=activity)
        bot.log.info(f"[READY] Logged in as {bot.user} (ID: {bot.user.id})")

    # Start the bot
    bot.run(token)


if __name__ == "__main__":
    main()
