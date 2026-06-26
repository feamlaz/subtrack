# SubTrack

Track all your subscriptions in the terminal.

Don't let subscriptions drain your wallet silently. SubTrack is a CLI/TUI app that keeps all your recurring payments in one place — with beautiful terminal UI, category breakdowns, renewal alerts, and export.

## Features

- Add, edit, remove subscriptions
- Categories: streaming, music, VPN, cloud, gaming, productivity, other
- Monthly / yearly cost breakdown by category
- Upcoming renewal alerts
- Multi-currency support (RUB, USD, EUR)
- Beautiful TUI dashboard (Textual)
- CLI for scripting and quick access
- Export to CSV / JSON
- All data stored locally in SQLite

## Install

```bash
pip install subtrack
```

## Quick Start

```bash
# Add a subscription
subtrack add "Netflix" --price 799 --currency RUB --category streaming --billing monthly

# List all
subtrack list

# Monthly summary
subtrack summary

# Launch TUI dashboard
subtrack tui

# Export
subtrack export --format csv --output subscriptions.csv
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `subtrack add` | Add a new subscription |
| `subtrack list` | List all subscriptions |
| `subtrack remove` | Remove a subscription |
| `subtrack edit` | Edit a subscription |
| `subtrack summary` | Show cost breakdown |
| `subtrack tui` | Launch interactive TUI |
| `subtrack export` | Export data (csv/json) |

## Tech Stack

- **Python 3.10+**
- **Textual** — TUI framework
- **Rich** — terminal formatting
- **Click** — CLI framework
- **SQLite** — local storage

## License

MIT
