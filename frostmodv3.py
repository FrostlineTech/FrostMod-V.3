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
                    "dadjokecog", "Activtycog", "publicinfo", "polls", "utilityimages", "minigames", "memes", "catcog", "dogcog",
                    # New enhancements
                    "errors", "diagnostics", "setup", "settings", "activity_digest", "moderation", "support", "aimodcog", "aihelpcog", "userprofilecog",
                    # New fun cogs
                    "trivia", "hangman", "scramble", "wyr"):
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
            log_voice_leave BOOLEAN NOT NULL DEFAULT FALSE,
            -- Expanded logging toggles
            log_bulk_delete BOOLEAN NOT NULL DEFAULT FALSE,
            log_channel_create BOOLEAN NOT NULL DEFAULT FALSE,
            log_channel_delete BOOLEAN NOT NULL DEFAULT FALSE,
            log_channel_update BOOLEAN NOT NULL DEFAULT FALSE,
            log_thread_create BOOLEAN NOT NULL DEFAULT FALSE,
            log_thread_delete BOOLEAN NOT NULL DEFAULT FALSE,
            log_thread_update BOOLEAN NOT NULL DEFAULT FALSE,
            -- Weekly digest channel
            digest_channel_id BIGINT,
            -- Moderation: modlog channel
            modlog_channel_id BIGINT,
            -- AI Moderation settings
            ai_moderation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            ai_temperature_threshold FLOAT NOT NULL DEFAULT 0.3,
            ai_warning_template TEXT,
            ai_low_severity_action TEXT DEFAULT 'warn', -- warn, delete, none
            ai_med_severity_action TEXT DEFAULT 'delete', -- warn, delete, none
            ai_high_severity_action TEXT DEFAULT 'delete', -- warn, delete, none
            ai_low_severity_threshold FLOAT DEFAULT 0.65,
            ai_med_severity_threshold FLOAT DEFAULT 0.75,
            ai_high_severity_threshold FLOAT DEFAULT 0.85,
            ai_include_message_context BOOLEAN DEFAULT FALSE,
            ai_context_message_count SMALLINT DEFAULT 3
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
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_bulk_delete BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_channel_create BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_channel_delete BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_channel_update BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_thread_create BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_thread_delete BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS log_thread_update BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS digest_channel_id BIGINT;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS modlog_channel_id BIGINT;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_moderation_enabled BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_temperature_threshold FLOAT NOT NULL DEFAULT 0.3;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_warning_template TEXT;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_low_severity_action TEXT DEFAULT 'warn';
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_med_severity_action TEXT DEFAULT 'delete';
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_high_severity_action TEXT DEFAULT 'delete';
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_low_severity_threshold FLOAT DEFAULT 0.65;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_med_severity_threshold FLOAT DEFAULT 0.75;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_high_severity_threshold FLOAT DEFAULT 0.85;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_include_message_context BOOLEAN DEFAULT FALSE;
        ALTER TABLE general_server ADD COLUMN IF NOT EXISTS ai_context_message_count SMALLINT DEFAULT 3;
        
        -- User Profiles migration: ensure all columns exist
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'user_profiles'
            ) THEN
                CREATE TABLE user_profiles (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT NOT NULL,
                    guilds JSONB NOT NULL DEFAULT '[]'::jsonb,
                    last_message_content TEXT,
                    last_message_guild_id BIGINT,
                    last_message_guild_name TEXT,
                    last_message_at TIMESTAMPTZ,
                    message_history JSONB NOT NULL DEFAULT '[]'::jsonb,
                    message_count INT NOT NULL DEFAULT 0,
                    activity_pattern JSONB NOT NULL DEFAULT '{}'::jsonb,
                    risk_assessment TEXT DEFAULT 'UNKNOWN',
                    risk_score FLOAT DEFAULT 0.0,
                    risk_factors JSONB NOT NULL DEFAULT '[]'::jsonb,
                    profile_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            ELSE
                -- Add any missing columns
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_profiles' AND column_name = 'risk_assessment'
                ) THEN
                    ALTER TABLE user_profiles ADD COLUMN risk_assessment TEXT DEFAULT 'UNKNOWN';
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_profiles' AND column_name = 'risk_score'
                ) THEN
                    ALTER TABLE user_profiles ADD COLUMN risk_score FLOAT DEFAULT 0.0;
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_profiles' AND column_name = 'risk_factors'
                ) THEN
                    ALTER TABLE user_profiles ADD COLUMN risk_factors JSONB NOT NULL DEFAULT '[]'::jsonb;
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'user_profiles' AND column_name = 'profile_updated_at'
                ) THEN
                    ALTER TABLE user_profiles ADD COLUMN profile_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
                END IF;
            END IF;
        END $$;

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

        -- Active polls persistence
        CREATE TABLE IF NOT EXISTS polls_active (
            message_id BIGINT PRIMARY KEY,
            channel_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            question TEXT NOT NULL,
            options JSONB NOT NULL,
            closed BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS polls_votes (
            message_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            option_idx INT NOT NULL,
            PRIMARY KEY (message_id, user_id)
        );

        -- MiniGames: persistent Connect 4 games
        CREATE TABLE IF NOT EXISTS games_connect4 (
            game_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            p1 BIGINT NOT NULL,
            p2 BIGINT NOT NULL,
            turn BIGINT NOT NULL,
            winner BIGINT,
            grid JSONB NOT NULL,
            finished BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Trivia: questions and scores
        CREATE TABLE IF NOT EXISTS trivia_questions (
            id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT, -- null = global question
            question TEXT NOT NULL,
            options JSONB NOT NULL, -- array of strings
            correct_idx INT NOT NULL,
            author_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS trivia_scores (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            score INT NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        -- Hangman: persistent games
        CREATE TABLE IF NOT EXISTS games_hangman (
            game_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            starter_id BIGINT NOT NULL,
            word TEXT NOT NULL,
            guessed JSONB NOT NULL, -- array of single-letter strings
            attempts_left INT NOT NULL,
            finished BOOLEAN NOT NULL DEFAULT FALSE,
            winner_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Scramble: persistent per-channel puzzle
        CREATE TABLE IF NOT EXISTS games_scramble (
            game_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            word TEXT NOT NULL,
            scrambled TEXT NOT NULL,
            finished BOOLEAN NOT NULL DEFAULT FALSE,
            winner_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Would You Rather: persistent vote counters
        CREATE TABLE IF NOT EXISTS games_wyr (
            game_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            prompt_a TEXT NOT NULL,
            prompt_b TEXT NOT NULL,
            count_a INT NOT NULL DEFAULT 0,
            count_b INT NOT NULL DEFAULT 0,
            finished BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        
        -- AI Moderation: user violation tracking
        CREATE TABLE IF NOT EXISTS ai_mod_violations (
            violation_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            channel_id BIGINT,
            violation_type TEXT NOT NULL, -- 'low', 'med', 'high'
            confidence FLOAT NOT NULL,
            message_content TEXT,
            reason TEXT,
            action_taken TEXT NOT NULL, -- 'warn', 'delete', 'none'
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        
        -- AI Moderation: rate limiting tracking
        CREATE TABLE IF NOT EXISTS ai_mod_rate_limits (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            violation_count INT NOT NULL DEFAULT 1,
            last_violation_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            current_limit_duration INT NOT NULL DEFAULT 5, -- seconds
            expires_at TIMESTAMPTZ,
            PRIMARY KEY (guild_id, user_id)
        );

        -- WYR per-user votes to prevent multiple votes
        CREATE TABLE IF NOT EXISTS games_wyr_votes (
            game_id BIGINT NOT NULL REFERENCES games_wyr(game_id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            choice CHAR(1) NOT NULL CHECK (choice IN ('A','B')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (game_id, user_id)
        );

        -- Ensure JSONB types on existing installs (in case older schemas used TEXT)
        DO $$
        BEGIN
            -- Add created_at to games_wyr_votes if missing
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'games_wyr_votes' AND column_name = 'created_at'
            ) THEN
                EXECUTE 'ALTER TABLE games_wyr_votes ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()';
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'games_hangman' AND column_name = 'guessed' AND data_type <> 'jsonb'
            ) THEN
                EXECUTE 'ALTER TABLE games_hangman ALTER COLUMN guessed TYPE JSONB USING guessed::jsonb';
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'games_connect4' AND column_name = 'grid' AND data_type <> 'jsonb'
            ) THEN
                EXECUTE 'ALTER TABLE games_connect4 ALTER COLUMN grid TYPE JSONB USING grid::jsonb';
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'trivia_questions' AND column_name = 'options' AND data_type <> 'jsonb'
            ) THEN
                EXECUTE 'ALTER TABLE trivia_questions ALTER COLUMN options TYPE JSONB USING options::jsonb';
            END IF;
        END $$;

        -- User Profiles: AI-based user profiling and risk assessment
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id BIGINT PRIMARY KEY,
            username TEXT NOT NULL,
            guilds JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of {guild_id, guild_name}
            last_message_content TEXT,
            last_message_guild_id BIGINT,
            last_message_guild_name TEXT,
            last_message_at TIMESTAMPTZ,
            message_history JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of recent messages for analysis
            message_count INT NOT NULL DEFAULT 0,
            activity_pattern JSONB NOT NULL DEFAULT '{}'::jsonb, -- Activity patterns by hour/day
            risk_assessment TEXT DEFAULT 'UNKNOWN', -- LOW, MEDIUM, HIGH, VERY HIGH, UNKNOWN
            risk_score FLOAT DEFAULT 0.0, -- 0-100 scale
            risk_factors JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of risk factors
            profile_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        
        -- Moderation: cases and timed roles
        CREATE TABLE IF NOT EXISTS mod_cases (
            case_id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT NOT NULL,
            target_id BIGINT NOT NULL,
            target_tag TEXT,
            moderator_id BIGINT NOT NULL,
            action TEXT NOT NULL, -- warn/mute/ban/unban/etc
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_mod_cases_guild_target ON mod_cases (guild_id, target_id, case_id DESC);

        CREATE TABLE IF NOT EXISTS timed_roles (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            role_id BIGINT NOT NULL,
            remove_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (guild_id, user_id, role_id)
        );
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
