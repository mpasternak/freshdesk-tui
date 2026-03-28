# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Freshdesk TUI is a terminal-based ticket browser for Freshdesk support portals, built with Python's Textual framework. It connects to the Freshdesk REST API v2 to list, search, filter, and view support tickets.

## Development Commands

```bash
# Run the app
uv run freshdesk-tui
uv run freshdesk-tui --filter open    # with initial status filter

# Install dependencies
uv sync
uv sync --group dev    # includes test dependencies

# Run tests
uv run pytest tests/ -v
```

## Architecture

The app is a single-package (`src/freshdesk_tui/`) with three modules:

- **`config.py`** — Loads Freshdesk credentials from env vars (`FRESHDESK_DOMAIN`, `FRESHDESK_API_KEY`) or `config.toml` (cwd or `~/.config/freshdesk-tui/`).
- **`api.py`** — Async Freshdesk API client using `httpx`. Dataclasses: `Ticket`, `Conversation`, `Attachment`. Uses Basic auth (API key + "X" password). Two listing strategies: `/tickets` endpoint with predefined filters, and `/search/tickets` for status-based queries.
- **`app.py`** — Textual `App` subclass (`FreshdeskTUI`). Two view modes: ticket list (DataTable) and ticket detail (VerticalScroll with Markdown-rendered HTML). CSS is defined inline in `MAIN_CSS`. HTML-to-markdown conversion uses `markdownify` with custom `<img>` tag handling.

## Key Patterns

- Freshdesk API responses use different field names: `description` = HTML, `description_text` = plain text, `body` = conversation HTML, `body_text` = conversation plain text.
- Status codes: 2=Open, 3=Pending, 4=Resolved, 5=Closed. Priority codes: 1=Low, 2=Medium, 3=High, 4=Urgent.
- `config.toml` is in `.gitignore` — it contains the API key. Never commit it.
- The app uses Textual's `@work` decorator for async API calls and `reactive` properties for state management.
