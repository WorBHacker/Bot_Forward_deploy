# BotF — Telegram Channel Broadcast & Moderation Bot

A production-ready Telegram bot that automatically moderates content from a master channel and broadcasts approved posts to a network of groups. Built with **aiogram 3**, **PostgreSQL**, and **Docker**.

---

## Features

### Content Moderation (2-stage pipeline)
- **Text / captions** — [Detoxify](https://github.com/unitaryai/detoxify) multilingual ML model (toxicity, insults, threats, obscenity). Runs on CPU or GPU.
- **Images / videos** — [Sightengine](https://sightengine.com) REST API (nudity, violence, weapons, drugs, alcohol). Skipped gracefully if no API key is set.

### Broadcasting
- Posts that pass moderation are forwarded to all active groups.
- Rate-limited queue (configurable, Telegram max is 30 msg/s).
- Media groups (albums) are collected and forwarded as a single batch.
- Manual broadcast via `/broadcast` command.

### Analytics
- Tracks views per post by scraping `t.me` every 30 minutes.
- Daily summary sent to the control panel at a configurable time (UTC).
- On-demand **Excel report** with full message statistics.

### Admin Panel (role-based access)
| Role | Permissions |
|---|---|
| **Owner** | Full access + GPU status + weekly DB backup |
| **SuperAdmin** | Manage admins and guests, view reports |
| **Admin** | Broadcast, view stats and groups |
| **Guest** | View daily stats only |

Commands: `/start`, `/help`, `/stats`, `/report`, `/broadcast`, `/list_groups`, `/list_users`, `/add_superadmin`, `/add_admin`, `/add_guest`, `/remove_user`, `/delete_group`, `/status`, `/backup`, `/lang`

### Scheduled Tasks (APScheduler)
- Daily text summary + Excel report
- Hub-channel view sync every 30 minutes
- Weekly PostgreSQL database backup (sent to owner via Telegram)

### Multilingual
- Russian and Uzbek interface (`/lang` to switch)

---

## Tech Stack

| Component | Library |
|---|---|
| Bot framework | [aiogram 3](https://docs.aiogram.dev) |
| Database | PostgreSQL 16 + asyncpg |
| ORM / migrations | SQLAlchemy (async) + Alembic |
| Scheduler | APScheduler |
| Text moderation | Detoxify (multilingual) |
| Media moderation | Sightengine API |
| Reports | pandas + openpyxl |
| Deployment | Docker + Docker Compose |

---

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Configure environment
```bash
cp .env.example .env
```
Open `.env` and fill in all required values (see comments in the file).

### 3. Run with Docker
```bash
docker compose up -d --build
```

The bot will:
1. Start a PostgreSQL container
2. Run Alembic migrations automatically
3. Launch the bot

### 4. Add yourself as owner
The `OWNER_ID` in `.env` is automatically the owner. Use `/start` in the control panel chat to verify.

---

## Project Structure

```
├── bot/
│   ├── handlers/          # Routers: admin panel, master channel, control panel, chat member
│   ├── services/          # Analytics, broadcaster, censorship, media collector
│   ├── middlewares/       # RBAC, i18n
│   ├── keyboards/         # Inline keyboards
│   ├── database/          # SQLAlchemy models and session
│   ├── utils/             # Backup, GPU monitor, localization texts
│   ├── config.py          # Pydantic settings (reads from .env)
│   └── main.py            # Entry point
├── alembic/               # Database migrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example           # Environment variable template
```

---

## Environment Variables

See [.env.example](.env.example) for the full list with descriptions.

Key variables:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `OWNER_ID` | Your Telegram user ID |
| `MASTER_CHANNEL_ID` | Channel to watch for new posts |
| `CONTROL_PANEL_CHAT_ID` | Chat where reports and alerts are sent |
| `DATABASE_URL` | PostgreSQL connection string |
| `SIGHTENGINE_API_USER` / `_SECRET` | Sightengine credentials (optional) |
| `DEVICE` | `cpu` or `cuda` for the Detoxify model |

---

## Moderation Thresholds

| Setting | Default | Description |
|---|---|---|
| `TOXICITY_THRESHOLD` | `0.7` | Detoxify score above which text is rejected |
| `NSFW_THRESHOLD` | `0.35` | Sightengine score above which media is rejected |

---

## License

MIT
