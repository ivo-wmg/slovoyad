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
