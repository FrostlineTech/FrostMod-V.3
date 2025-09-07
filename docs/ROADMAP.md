# FrostMod Roadmap

A focused plan for upcoming improvements to FrostMod. Timelines are indicative and may adjust as we validate features with real servers.

## Non-Goals

- No web backend or external dashboard. All configuration happens in Discord via slash commands and UI components.
- No paywalls/premium tiers. All features remain free and accessible.

## 1) Logging & Moderation enhancements

- [x] Centralized `/logs` UI (channel picker + per-toggle settings)
- [x] Bulk delete, channel/thread create/delete/update listeners
- [x] Verbose embeds with IDs, diffs, jump links, and actor attribution via audit logs
- [x] Connect Local Deepseek model for AI moderation (warn and delete inappropriate messages)
- [x] Implemented `/testmod` command to test AI moderation
- [x] Implemented `/disabletheta` to enable/disable AI moderation per server
- [x] Added `/modstats` to view AI moderation performance metrics
- [ ] Implement `/modlog` command to view moderation logs

## 2) UX & Configuration

- [ ] Read-only command to view current config (channels, toggles)
- [ ] Inline help in `/logs` UI (mini legend + tooltips)
- [ ] Localized labels and messages (en-US first; structure for additional locales)

## 3) Reliability & Testing

- [ ] Add unit tests for DB accessors and toggle persistence
- [ ] Add integration tests for listeners using mock guild/channel/thread
- [ ] Fuzz/edge-case tests for permission errors, missing channels, and partial data

## 4) Performance & Observability

- [ ] Structured metrics: counts for events (joins/leaves, deletions, updates)
- [ ] Sampling/aggregation for high-volume events to avoid spam
- [ ] Extended logging for slow DB queries and Discord REST retries

## 5) Database & Migrations

- [x] Idempotent schema ensures for existing tables/columns
- [ ] Optional migration scripts for manual ops (SQL files under `db/`)
- [ ] Housekeeping job to prune old event logs (if persisted later)

## 6) Permissions & Safety

- [ ] Pre-flight permission checks for `/logs` (e.g., View Audit Log) with actionable guidance
- [ ] Graceful fallbacks when actor attribution isn’t available
- [ ] Guardrails for purge and bulk operations (cooldowns, audit fields)

## 7) Release & Docs

- [x] Update README with Logging section and schema details
- [x] Polish Best Practices with audit enrichment and unified voice logging
- [x] Create roadmap document
- [ ] Add screenshots/gifs of the `/logs` UI in README
- [ ] Changelog for each release with migration notes

## 8) AI & User Profiling

- [x] Implement `/aiexplain` command to explain AI moderation decisions
- [x] Implement `/risklevel` command to view user risk levels
- [x] Create user profiling system that tracks message patterns and guild activity
- [x] Develop AI-based risk assessment with multiple risk factors
- [x] Ensure timezone-aware datetime handling for all user analytics
- [x] Implement channel-specific moderation settings with `/channelmod` command
- [x] Add message pattern recognition to detect content split across multiple messages
- [x] Implement activity pattern analysis for anomaly detection
- [x] Add social connection analysis to detect networks of high-risk users
- [x] Create AI-powered help system with `/ask` and `/askabout` commands
- [ ] Add moderation actions triggered by high risk levels
- [ ] Implement customizable risk thresholds per server
- [x] Implement `/modstats` command to view AI moderation statistics

## 9) Nice-to-haves

- [ ] Export/import guild config (JSON) for migrations between servers
- [ ] Advanced filters (ignore channels/roles/users for specific log types)
