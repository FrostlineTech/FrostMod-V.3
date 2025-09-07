# FrostMod — Discord Moderation Bot

A Python Discord bot built with discord.py that provides moderation utilities, welcome/leave automation, and autorole assignment with PostgreSQL persistence via asyncpg.

## Features

- Welcome messages with configurable channel and template
- Leave messages with configurable channel and template
- Autorole assignment on member join
- Purge command for bulk message deletion
- PostgreSQL-backed configuration and audit logs (joins/leaves)
- Structured logging and developer-guild fast command sync
- Centralized, toggleable logging UI for many events (see Logging)
- AI moderation using local DeepSeek model to detect and remove inappropriate messages
- Advanced pattern recognition to detect content split across multiple messages
- Channel-specific moderation settings with customizable strictness levels
- User profiling system that tracks message patterns and guild activity
- Risk assessment using AI to identify potentially problematic users
- Activity pattern analysis for anomaly detection
- Social connection analysis to detect networks of high-risk users
- AI-powered help system for answering server-specific questions

## Requirements

- Python 3.11+ (tested with 3.13)
- PostgreSQL 12+
- A Discord bot token
- DeepSeek model running locally via text-generation-webui (for AI moderation)
- NVIDIA GPU recommended (optimized for RTX 3060)

## Setup

1. Clone/download the repo and install dependencies:

```bash
python -m pip install -r requirements.txt
```

1. Create a `.env` in the project root:

```env
DISCORD_TOKEN=YOUR_BOT_TOKEN
Developer_Guild_ID=YOUR_DEV_GUILD_ID
DB_NAME=frostmoddb
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# AI Moderation settings
Local_model=your_deepseek_model_name
AI_API_URL=http://127.0.0.1:5000
ai_api_path=/v1/chat/completions
```

1. Initialize the database (choose one):

- Automatic: the bot creates/ensures tables at startup (idempotent)
- Manual: open `Schema.sql` in pgAdmin and run it

## Running

- Windows (console with blue text, UTF-8, unbuffered logs):

```bat
Start_frostmod.bat
```

- Directly with Python:

```bash
python -u frostmodv3.py
```

## Slash Commands

- `/welcome channel <#channel>` — Set welcome channel
- `/welcome message <template>` — Set welcome template

  - Placeholders: `{user}`, `{guild}`, `{membercount}`

- `/welcome setup` — Interactive setup UI (admin): choose channel via selector and edit template via modal; saves to DB
- `/leave channel <#channel>` — Set leave channel
- `/leave message <template>` — Set leave template
- `/leave setup` — Interactive setup UI (admin): choose channel via selector and edit template via modal; saves to DB
- `/purge <1-200>` — Delete recent messages (admin)
- `/jrole <@role>` — Set role to auto-assign on join (admin)
- `/status` — Show uptime and websocket latency
- `/db` — Check database connectivity and latency (admin)
- `/help` — Admin help with setup guide and troubleshooting (ephemeral)
- `/serverinfo` — Show server details (name, ID, owner, members, boosts, channels, roles, emojis, created)

- `/logs` — Configure logs channel and toggle log types with an interactive UI (admin)
- `/webstatus` — Check website heartbeat/latency (outbound-only; no hosting)
- `/disabletheta` — Enable/disable AI moderation for the server (admin)
- `/testmod` — Test the AI moderation on a provided message (admin)
- `/modstats` — View AI moderation statistics and performance metrics (admin)
- `/channelmod [#channel]` — Configure channel-specific moderation settings (admin)
- `/risklevel <@user>` — Get an AI-based risk assessment for a user (admin only)
- `/ask` — Ask the AI assistant a question about the server
- `/askabout <topic>` — Ask about a specific topic with context-aware responses
- `/aiexplain` — Learn how AI moderation works in detail

All commands are guild-only and require appropriate permissions (e.g., Manage Guild, Manage Messages).

## Database Schema

Tables:

- `general_server(guild_id, guild_name, join_role_id, welcome_channel_id, leave_channel_id, welcome_message, leave_message,
  logs_channel_id,
  log_message_delete, log_message_edit,
  log_nickname_change, log_role_change, log_avatar_change,
  log_member_join, log_member_leave,
  log_voice_join, log_voice_leave,
  log_bulk_delete,
  log_channel_create, log_channel_delete, log_channel_update,
  log_thread_create, log_thread_delete, log_thread_update)`
- `user_joins(user_id, user_name, guild_id, guild_name, joined_at)`
- `user_leaves(user_id, user_name, guild_id, guild_name, left_at)`
- `user_profiles(user_id, username, guilds, last_message_content, last_message_guild_id, last_message_guild_name, last_message_at, message_history, message_count, activity_pattern, risk_assessment, risk_score, risk_factors, profile_updated_at, created_at)`

Indexes:

- `idx_user_joins_guild_time(guild_id, joined_at DESC)`
- `idx_user_leaves_guild_time(guild_id, left_at DESC)`

The bot performs idempotent schema ensures at startup. Optionally, you can maintain SQL scripts for manual setup.

## Project Constraints

- No web backend: all configuration is done in Discord via slash commands and UI components; infrastructure is limited to the bot process and PostgreSQL.
- No paywalls/premium tiers: all features are available without payment gates. Keep the project fully functional with open configuration.

Note: The `Webserver` cog is a simple outbound heartbeat checker for your website (no web server hosted by the bot).

## Logging

Use `/logs` to select the logs channel and toggle specific events. The bot posts branded embeds with useful context (IDs, timestamps, links, actor when resolvable via audit logs).

__Supported toggles:__

- Message delete, message edit
- Nickname change, role change, avatar change
- Member join, member leave (with kick/ban detection when possible)
- Voice join, voice leave/move
- Bulk message delete
- Channel create/delete/update
- Thread create/delete/update

Notes:

- Some actor fields require “View Audit Log” permission.
- Embeds include compact diffs for updates (e.g., channel/thread changes) and jump links where applicable.

## Configuration & Logging

- Logs are emitted via Python `logging` with a concise format. All database reads/writes are instrumented.
- Developer guild ID enables immediate command sync in that guild while global sync propagates.

## Troubleshooting

- Bot starts but DB fails: check `.env` vars and connectivity. If your password has special chars, we pass parameters directly to asyncpg to avoid DSN encoding issues.
- Slash commands not visible: ensure the bot has application.commands, you’re in a guild, and wait for global propagation; dev guild should be instant.
- Autorole didn’t apply: ensure the bot’s highest role is ABOVE the target role and it has “Manage Roles”. Check logs for detailed role assignment diagnostics.
- Welcome/leave embed missing: verify configured channels and bot permissions to send messages and embeds in those channels.
- No logs appearing: set a logs channel with `/logs` and ensure relevant toggles are enabled. For actor fields, grant the bot “View Audit Log”.
- Check connectivity quickly with admin-only diagnostics:

  - Run `/health` to see websocket latency and interaction RTT.
  - Run `/db` to verify DB pool connectivity and ping.

## License

For private/internal use. Replace this section with your preferred license if needed.
