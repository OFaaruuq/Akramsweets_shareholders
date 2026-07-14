# Akram Sweets — Shareholders

Flask web app for **Akram Sweets** shareholder management: profit periods, shareholding records, portal access, and scheduled PDF reports.

## Features

- Admin dashboard for shareholders, users, and reporting periods
- Shareholder portal for viewing personal statements
- Brand settings (logo, company details)
- Scheduled email report delivery
- Docker Compose stack (PostgreSQL, app, nginx, report scheduler)

## Requirements

- Python 3.9+
- Node.js 18+ (for frontend asset build via Gulp)
- Docker & Docker Compose (recommended)

## Quick start (Docker)

```bash
cp env.sample .env
docker compose up --build -d
```

App (via nginx): [http://localhost:5085](http://localhost:5085)

## Local development

```bash
# 1. Python deps
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt

# 2. Environment
cp env.sample .env

# 3. Frontend assets (optional if static CSS already built)
yarn install
# or: npm install --legacy-peer-deps

# 4. Run
flask --app run.py run --debug
# or
python run.py
```

Default local DB is SQLite (see `env.sample`). For PostgreSQL, uncomment the DB settings in `.env` or use Docker Compose.

## Project layout

```
apps/
  auth/           Login & access
  shareholders/   Shareholder CRUD
  periods/        Profit periods
  reports/        Report generation
  portal/         Shareholder self-service
  users/          User management
  app_settings/   System & brand settings
  static/         CSS, JS, images
  templates/      Jinja templates
scripts/          DB setup & scheduled reports
nginx/            Reverse proxy config
docker-compose.yml
```

## Environment

Copy `env.sample` to `.env` and adjust. Never commit `.env` — it is gitignored.

| Variable | Purpose |
|----------|---------|
| `DEBUG` | `True` for development |
| `SECRET_KEY` | Flask secret (set in production) |
| `DB_*` / `DATABASE_URL` | Database connection |
| `MAIL_*` | Optional SMTP (also configurable in Settings → System) |

## Production notes

- Set `DEBUG=False` and a strong `SECRET_KEY`
- Use PostgreSQL (Docker Compose included)
- Change default DB passwords in `docker-compose.yml` before deploying
- Expose only nginx (port 5085), not the app container directly

## License

Private project for Akram Sweets. All rights reserved unless otherwise agreed.
