# Akram Sweets — Shareholders

Flask web app for **Akram Sweets** shareholder management: profit periods, shareholding records, portal access, and scheduled PDF reports.

## Features

- Admin dashboard for shareholders, users, and reporting periods
- Contacts directory (shareholders + staff, searchable by country)
- Shareholder portal for viewing personal statements
- Brand settings (logo, company details)
- Dynamic certificate content settings
- Monthly **Mudarabah** distribution from Odoo Net Profit (configurable pool % × ownership %) — see [docs/MUDARABAH.md](docs/MUDARABAH.md) and [docs/NET_PROFIT_DISTRIBUTION.md](docs/NET_PROFIT_DISTRIBUTION.md)
- Special arrangements on the shareholders’ pool — see [docs/SPECIAL_ARRANGEMENTS.md](docs/SPECIAL_ARRANGEMENTS.md)
- Dynamic **share value** (e.g. 1 share = 1000) — see [docs/SHARE_VALUE.md](docs/SHARE_VALUE.md)
- Login email OTP verification (requires SMTP)
- Alembic database migrations (`flask db upgrade`)
- Scheduled email report delivery
- Local **PostgreSQL** database

## Requirements

- Python 3.9+
- PostgreSQL 14+ (local install)
- Node.js 18+ (optional, for frontend asset build via Gulp)

## Local setup

```bash
# 1. Python deps
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Environment
cp env.sample .env
# Edit .env if your Postgres host/port/user differ

# 3. Create database + role (needs postgres superuser once)
sudo -u postgres psql -f scripts/init_postgres.sql
# or: sudo -u postgres python scripts/setup_database.py

# 4. Frontend assets (optional if static CSS already built)
yarn install
# or: npm install --legacy-peer-deps

# 5. Run
flask --app run.py run --debug
# or: python run.py
```

App URL: [http://127.0.0.1:5000](http://127.0.0.1:5000)

Default seed logins (after first start):

| Email | Password |
|-------|----------|
| `admin@akramsweets.com` | `admin123` |
| `finance@akramsweets.com` | `finance123` |

### Create a super admin

```bash
python scripts/create_super_admin.py
# or non-interactive:
python scripts/create_super_admin.py --email you@company.com --name "Your Name" --password 'StrongPass123!' --force
```

## Project layout

```
apps/
  auth/           Login & access
  shareholders/   Shareholder CRUD
  periods/        Monthly Mudarabah profit periods
  reports/        Certificates & distribution reports
  portal/         Shareholder self-service home
  contacts/       Staff directory (people contacts)
  users/          User & role management
  app_settings/   System, brand, arrangements, display KPIs
  services/       Domain logic (calc, ownership, OTP, mail, …)
  static/         CSS, JS, images
  templates/      Jinja templates
docs/             Mudarabah, arrangements, distribution guides
scripts/          DB setup, verify_app, scheduled reports
```

## Environment

Copy `env.sample` to `.env` and adjust. Never commit `.env` — it is gitignored.

| Variable | Purpose |
|----------|---------|
| `DEBUG` | `True` for development |
| `SECRET_KEY` | Flask secret (set in production) |
| `DB_*` / `DATABASE_URL` | Local PostgreSQL connection |
| `MAIL_*` | Optional SMTP (also configurable in Settings → System) |

## Production notes

- Set `DEBUG=False` and a strong `SECRET_KEY` (required; 16+ characters)
- Use PostgreSQL with a strong `DB_PASS` (special characters are URL-encoded automatically for `DB_*`)
- Keep PostgreSQL bound to localhost or behind a firewall
- Configure SMTP (`MAIL_*`) before enabling login OTP (`LOGIN_OTP_ENABLED=true`)
- Apply schema changes with Alembic before or on first boot:
  `flask --app run.py db upgrade`
- Prefer `gunicorn wsgi:app` (also works with `gunicorn run:app`)
- Run the report scheduler separately: `python scripts/send_scheduled_reports.py` (cron/systemd)

### Database migrations

```bash
# Apply pending revisions (clean server or upgrades)
flask --app run.py db upgrade

# After model changes
flask --app run.py db migrate -m "describe change"
flask --app run.py db upgrade
```

Destructive local rebuild (DEBUG only, wipes data):

```bash
ALLOW_SCHEMA_RESET=true flask --app run.py run
```

### Clean server checklist

1. Install PostgreSQL and create DB/role (`scripts/init_postgres.sql` or `scripts/setup_database.py`)
2. `cp env.sample .env` and set `SECRET_KEY`, `DB_*` / `DATABASE_URL`, `MAIL_*`
3. `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
4. `flask --app run.py db upgrade`
5. `gunicorn wsgi:app` (or `flask --app run.py run` for DEBUG)

## License

Private project for Akram Sweets. All rights reserved unless otherwise agreed.
