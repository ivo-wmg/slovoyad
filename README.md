# Slovoyad

Automated article evaluation tool for Bulgarian media websites.

**Supported domains:** news.bg, money.bg, infostock.bg, topsport.bg, lifestyle.bg, chr.bg, webcafe.bg, mamamia.bg

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python migrate.py
uvicorn app:app --reload --port 8000
```

## Migrations

SQL migration files live in `migrations/`. They are tracked via a `_migrations` table.

```bash
python migrate.py              # Apply all pending migrations
python migrate.py status       # Show which are applied/pending
python migrate.py create "description"  # Create new empty migration
```

## Deploy (production)

```bash
ssh rabota.wmgcorp.eu "cd ~/slovoyad.wmgcorp.eu && git pull && /home/usmivkat/virtualenv/slovoyad.wmgcorp.eu/3.9/bin/python migrate.py && touch tmp/restart.txt && echo DEPLOYED"
```

**Steps:**
1. `git pull` — pull latest code
2. `python migrate.py` — apply pending DB migrations
3. `touch tmp/restart.txt` — restart Passenger app server
