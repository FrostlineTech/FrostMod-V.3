# FrostMod Roadmap

A focused plan for upcoming improvements to FrostMod. Timelines are indicative and may adjust as we validate features with real servers.

## Non-Goals

- No web backend or external dashboard. All configuration happens in Discord via slash commands and UI components.
- No paywalls/premium tiers. All features remain free and accessible.

## 1) Logging Enhancements

- [x] Centralized `/logs` UI (channel picker + per-toggle settings)
- [x] Bulk delete, channel/thread create/delete/update listeners
- [x] Verbose embeds with IDs, diffs, jump links, and actor attribution via audit logs
- [ ] Emoji & sticker events (create/delete/update) with toggles
- [ ] Webhook events (create/update/delete) with toggles
- [ ] Server boosts and tier changes
- [ ] Message pin/unpin and reaction add/remove (rate-limit aware)
- [ ] Optional verbosity levels (Compact vs Detailed) toggle in `/logs`

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

## 8) Nice-to-haves

- [ ] Export/import guild config (JSON) for migrations between servers
- [ ] Advanced filters (ignore channels/roles/users for specific log types)
