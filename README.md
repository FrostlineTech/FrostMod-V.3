# FrostMod — Discord Moderation Bot

A Python Discord bot built with discord.py that provides moderation utilities, welcome/leave automation, and autorole assignment with PostgreSQL persistence via asyncpg.

## Features

- Welcome messages with configurable channel and template
- Leave messages with configurable channel and template
- Autorole assignment on member join
- Purge command for bulk message deletion
- PostgreSQL-backed configuration and audit logs (joins/leaves)
- Structured logging and developer-guild fast command sync

## Requirements

- Python 3.11+ (tested with 3.13)
- PostgreSQL 12+
- A Discord bot token

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

All commands are guild-only and require appropriate permissions (e.g., Manage Guild, Manage Messages).

## Database Schema

Tables:

- `general_server(guild_id, guild_name, join_role_id, welcome_channel_id, leave_channel_id, welcome_message, leave_message)`
- `user_joins(user_id, user_name, guild_id, guild_name, joined_at)`
- `user_leaves(user_id, user_name, guild_id, guild_name, left_at)`

Indexes:

- `idx_user_joins_guild_time(guild_id, joined_at DESC)`
- `idx_user_leaves_guild_time(guild_id, left_at DESC)`

See `Schema.sql` for a full drop-and-recreate script suitable for pgAdmin.

## Configuration & Logging

- Logs are emitted via Python `logging` with a concise format. All database reads/writes are instrumented.
- Developer guild ID enables immediate command sync in that guild while global sync propagates.

## Troubleshooting

- Bot starts but DB fails: check `.env` vars and connectivity. If your password has special chars, we pass parameters directly to asyncpg to avoid DSN encoding issues.
- Slash commands not visible: ensure the bot has application.commands, you’re in a guild, and wait for global propagation; dev guild should be instant.
- Autorole didn’t apply: ensure the bot’s highest role is ABOVE the target role and it has “Manage Roles”. Check logs for detailed role assignment diagnostics.
- Welcome/leave embed missing: verify configured channels and bot permissions to send messages and embeds in those channels.
- Check connectivity quickly with admin-only diagnostics:

  - Run `/health` to see websocket latency and interaction RTT.
  - Run `/db` to verify DB pool connectivity and ping.

## License

For private/internal use. Replace this section with your preferred license if needed.
