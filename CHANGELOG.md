# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Docs polish: README Logging section, Project Constraints, `/webstatus` documented
- Best Practices updated: centralized `/logs` UI, audit enrichment, constraints
- Roadmap added with Non-Goals (no web backend, no paywalls)

## 0.3.0

- Expanded logging toggles and listeners (bulk delete; channel/thread create/delete/update)
- Verbose embeds (IDs, diffs, jump links, actor + reason via audit logs)
- Unified voice logs under main logging cog
- Idempotent DB migrations for new toggle columns

## 0.2.0

- Added `/serverinfo`, `/status`, `/db` diagnostics
- Autorole onboarding improvements and structured logging

## 0.1.0

- Initial features: welcome/leave, autorole, purge, basic schema
