# Freshdesk TUI

A terminal-based ticket browser for [Freshdesk](https://freshdesk.com/) support portals.

Browse, search, filter, and view your Freshdesk support tickets without leaving the terminal.

## Disclaimer

I am **not** affiliated with Freshdesk or Freshworks in any way. I just like their services very much and I suggest their helpdesk solution to everyone.

## Features

- Browse tickets in a sortable table view
- View full ticket details with conversations rendered as Markdown
- Filter tickets by status (Open, Pending, Resolved, Closed)
- Search tickets by subject, number, requester, or tags
- Open tickets in browser
- Browse and open attachments
- Pagination support

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
# Clone the repository
git clone https://github.com/mpasternak/freshdesk-tui.git
cd freshdesk-tui

# Install with uv
uv sync
```

## Configuration

You need a Freshdesk API key. You can find it in your Freshdesk profile settings.

### Option 1: Config file (recommended)

Copy the sample config and fill in your credentials:

```bash
cp config.toml.sample config.toml
```

Edit `config.toml`:

```toml
[freshdesk]
domain = "yourcompany.freshdesk.com"
api_key = "your_api_key_here"
```

The app searches for `config.toml` in:
1. Current working directory
2. `~/.config/freshdesk-tui/config.toml`

### Option 2: Environment variables

```bash
export FRESHDESK_DOMAIN="yourcompany.freshdesk.com"
export FRESHDESK_API_KEY="your_api_key_here"
```

Environment variables take precedence over the config file.

## Usage

```bash
uv run freshdesk-tui
```

Start with a specific status filter:

```bash
uv run freshdesk-tui --filter open
uv run freshdesk-tui --filter closed
uv run freshdesk-tui --filter all
```

## Keyboard Shortcuts

| Key       | Action                          |
|-----------|---------------------------------|
| `Enter`   | View ticket details             |
| `Escape`  | Go back / close                 |
| `/`       | Search tickets                  |
| `s`       | Cycle status filter             |
| `o`       | Open ticket in browser          |
| `a`       | Browse attachments              |
| `r`       | Refresh ticket list             |
| `n` / `p` | Next / previous page            |
| `q`       | Quit                            |

## License

MIT
