# Best Practices for Discord Bots in Python (discord.py)

This project follows a set of practices that make your bot reliable, maintainable, and secure. Below is a concise guide to the “why” behind architectural and implementation choices.

## Architecture & Structure

- **Cogs (modular features)**: Commands and listeners are split into cogs like `Welcomecog.py`, `Leavecog.py`, and `autorolecog.py`. This keeps features isolated, easier to test, and maintain.
- **Single entrypoint (`frostmodv3.py`)**: Centralizes startup concerns: environment loading, logging config, DB initialization, extension loading, and application command syncing.
- **Centralized logging UI (`deletedmescog.py`)**: A single `/logs` command hosts a configuration view (`LogsConfigView`) for channel selection and per-toggle log settings that persist to PostgreSQL.
- **Configuration via `.env`**: Secrets (token, DB creds) are not hardcoded. They’re loaded securely with `python-dotenv`.

## Slash Commands & Syncing

- **Slash (app) commands**: Modern, auto-documented by Discord. We restrict to guild-only and set default permissions (`manage_guild`, `manage_messages`) to surface commands to the right users.
- **Developer guild fast sync**: In `setup_hook`, we sync globally and then copy globals to a developer guild for instant iteration.

## Database & Persistence

- **Async PostgreSQL (`asyncpg`)**: Fully async DB driver. We create a pool once and re-use it across cogs via `bot.pool`.
- **Idempotent schema ensure**: On startup, the bot ensures tables exist—safe to run repeatedly and avoids manual steps in development. New columns for log toggles are added idempotently.
- **Prepared writes/reads**: All DB ops use bound parameters to avoid injection risks and to help the server cache execution plans.

## Logging & Observability

- **Structured logging**: Configured in `frostmodv3.py` with timestamps and levels. Every DB read/write is logged for traceability.
- **Actionable diagnostics**: Autorole logs include role hierarchy context and reasons when assignment is skipped.
- **Toggleable event logging**: Bulk deletes, channel/thread create/delete/update, message edits/deletes, joins/leaves, voice joins/leaves. Each toggle is persisted per guild in `general_server`.
- **Audit log enrichment**: Where applicable, audit logs are queried to attribute an action to an executor and include a reason (requires "View Audit Log").
- **Consistent, richer embeds**: Embeds include IDs, timestamps, jump links (where available), and concise diffs for updates, using shared branding (`BRAND_COLOR`, `FOOTER_TEXT`).
- **Unified voice logging**: Voice join/leave/move is handled in a unified cog to avoid duplicate logs.

## Permissions & Security

- **Principle of least privilege**: Commands are permission-gated; the bot only needs intents and permissions required for features.
- **Role hierarchy awareness**: Role assignment checks `me.top_role` vs target role to avoid forbidden errors.
- **Secret handling**: `.env` and `.gitignore` ensure secrets aren’t committed.
- Ensure the bot has "View Audit Log" if you want actor attribution in logs.

## Project Constraints

- **No web backend**: All configuration and operations happen inside Discord (slash commands, UI components). No separate web server or dashboard is planned.
- **No paywalls**: No premium tiers or feature gates. All capabilities remain free and accessible when the bot is deployed.

## Embeds & UX

- **Consistent styling**: Shared cobalt blue brand color (centralized in `branding.py` as `BRAND_COLOR`) and standard footer text ensure consistent, polished embeds.
- **Ephemeral confirmations**: Administrative commands acknowledge privately to reduce channel noise while still giving operators feedback.
- **Admin UI**: Use select menus, buttons, and modals with clear labels and success/secondary color semantics for ON/OFF.

## Error Handling

- **Fail soft**: Listeners handle HTTP exceptions and continue without crashing the bot.
- **Clear warnings**: Logs highlight missing configuration (e.g., DB not set), missing permissions, or hierarchy constraints.

## Performance & Concurrency

- **Connection pooling**: Re-use DB connections for efficient IO.
- **Async throughout**: All IO uses `await` to keep the bot responsive even under load.

## Local Development

- **Start script (`Start_frostmod.bat`)**: Colored console, UTF-8, and unbuffered output for real-time logs.
- **Schema.sql**: Full drop-and-recreate script for easy DB resets during testing.

## Future Enhancements

- **Metrics**: Add Prometheus or simple counters for joins/leaves and command usage.
- **Health checks**: Use the `/status` command for latency/uptime and consider background tasks to verify DB availability.
- **Config viewing**: Add read-only commands to display current guild config.
- **Verbosity levels**: Add a compact/detailed switch in `/logs` to tailor embed detail.

By following these practices, your Discord bot remains robust, secure, and easy to evolve as requirements change.
