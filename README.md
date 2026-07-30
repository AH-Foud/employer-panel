# Employer Panel — Bale Bot + Web Dashboard

A Bale (Telegram-compatible) bot and web dashboard for employer-user communication with SOP automation.

## Quick Install

```bash
bash <(curl -s https://raw.githubusercontent.com/AH-Foud/employer-panel/main/install.sh)
```

**Requirements:** Ubuntu 20+/Debian 11+, root access, port 80 open (for SSL).

## After Install

1. Edit `/opt/employer-panel/config.py` — set your real `BOT_TOKEN` and `ADMIN_ID`
2. Run `karpanel` for management menu
3. Access the web dashboard at the URL shown

## Features

- User → employer messaging with auto-forwarding
- SOP (Standard Operating Procedure) keyword matching & auto-reply
- Employer management with invite links
- Web dashboard with analytics, user management
- SQLite database (no extra setup required)
- Auto SSL via Let's Encrypt (acme.sh)
- `karpanel` management command
