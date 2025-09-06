# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### AI Moderation and Analysis

- AI moderation using local DeepSeek model to detect and remove inappropriate content
- Added `/disabletheta` command to enable/disable AI moderation per server
- Added `/testmod` command to test AI moderation on sample messages
- Added `/modstats` command to view AI moderation statistics and hardware metrics
- Implemented user profiling system that tracks message patterns and guild activity
- Added `/risklevel` command for admins to assess potential user risks using AI
- Automatic risk factor identification based on message content and behavior patterns

### Technical Improvements

- Hardware-aware optimization for NVIDIA RTX 3060 GPU and other system configurations
- Robust error handling for AI service connections and response parsing
- Consistent timezone handling for all datetime comparisons
- Improved JSON parsing with multiple fallback extraction methods

### Documentation Updates

- Docs polish: README Logging section, Project Constraints, `/webstatus` documented
- Best Practices updated: centralized `/logs` UI, audit enrichment, constraints, AI moderation guidelines
- Added user profiling best practices and ethical usage guidelines
- Roadmap updated with completed AI moderation and user profiling features

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
