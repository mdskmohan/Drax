# FitBot — Complete Setup Guide

## Prerequisites
- Python 3.11+
- Docker + Docker Compose
- Telegram Bot Token (from @BotFather)
- DeepSeek API Key
- Nutritionix App ID + API Key (optional but recommended)
- YouTube Data API Key (optional)

---

## Step 1: Get Your Telegram Bot Token

1. Open Telegram → search `@BotFather`
2. Send `/newbot`
3. Choose a name: `My FitBot`
4. Choose a username: `myfitbot_yourname_bot`
5. Copy the token → paste into `.env`

---

## Step 2: Get Your DeepSeek API Key

1. Go to https://platform.deepseek.com
2. Sign up / Log in
3. API Keys → Create new key
4. Copy it → paste into `.env`

---

## Step 3: Get Nutritionix Keys (Optional but recommended)

1. Go to https://developer.nutritionix.com
2. Sign up for free developer account
3. Get App ID and API Key
4. Add to `.env`

---

## Step 4: Get YouTube API Key (Optional)

1. Go to https://console.cloud.google.com
2. Create project → Enable "YouTube Data API v3"
3. Credentials → Create API Key
4. Add to `.env`

---

## Step 5: Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys
nano .env
```

Required keys:
```
TELEGRAM_BOT_TOKEN=your_token_here
DEEPSEEK_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://fitbot:fitbot_pass@db:5432/fitbot_db
DATABASE_SYNC_URL=postgresql://fitbot:fitbot_pass@db:5432/fitbot_db
REDIS_URL=redis://redis:6379/0
```

---

## Step 6: Local Development (Polling Mode — No server needed)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis only
docker-compose up db redis -d

# Update .env to use localhost for local dev:
# DATABASE_URL=postgresql+asyncpg://fitbot:fitbot_pass@localhost:5432/fitbot_db
# REDIS_URL=redis://localhost:6379/0

# Run the bot in polling mode
python run_polling.py
```

The bot will start accepting messages immediately via polling (no webhook needed for local dev).

---

## Step 7: Production Deployment (Docker)

```bash
# 1. Set TELEGRAM_WEBHOOK_URL in .env
# Example: https://yourdomain.com
# The app will auto-set: https://yourdomain.com/webhook

# 2. Build and start all services
docker-compose up --build -d

# 3. Check logs
docker-compose logs -f web
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat

# 4. Check health
curl http://localhost:8000/health
```

---

## Step 8: Database Migrations (if schema changes)

```bash
# Auto-generate migration
alembic revision --autogenerate -m "initial_schema"

# Apply migration
alembic upgrade head
```

---

## Architecture Overview

```
User (Telegram)
      │
      ▼
FastAPI Webhook (/webhook)
      │
      ▼
Bot Router (app/bot/bot.py)
      │
   ┌──┴──────────────────────────┐
   │                             │
Handlers                      Handlers
(onboarding, meals,           (water, workouts,
 progress, general)            motivation)
   │                             │
   └──────────┬──────────────────┘
              │
           Agents
    ┌─────────┼─────────┐
    │         │         │
 Fitness   Nutrition  Hydration
 Coach     Agent      Agent
    │         │         │
    └─────────┼─────────┘
              │
         DeepSeek API
              │
       Nutritionix / YouTube
              │
         PostgreSQL
```

---

## Daily Loop

| Time (IST) | Event |
|-----------|-------|
| 7:00 AM | Morning plan + meal plan sent |
| Every 2h | Water reminders (if behind) |
| 5:30 PM | Pre-gym motivation |
| 9:00 PM | Evening check-in (workout done? calories/water?) |
| Sunday 8AM | Weekly progress report |

---

## Bot Commands

| Command | Description |
|---------|-------------|
| /start | Onboarding or main menu |
| /menu | Show main menu |
| /plan | Today's full plan |
| /meal | Log a meal |
| /water | Log water intake |
| /workout | Today's workout |
| /weight | Log your weight |
| /progress | View progress |
| /report | Weekly report |
| /motivation | Get motivated |
| /help | Help |

---

## Troubleshooting

**Bot not responding?**
- Check `TELEGRAM_BOT_TOKEN` is correct
- In polling mode: ensure `run_polling.py` is running
- In webhook mode: ensure your server is reachable at `TELEGRAM_WEBHOOK_URL`

**Database errors?**
- Ensure PostgreSQL is running: `docker-compose ps db`
- Check `DATABASE_URL` matches your setup

**DeepSeek errors?**
- Verify `DEEPSEEK_API_KEY` is valid
- Check API quota at platform.deepseek.com

**Celery not scheduling?**
- Ensure Redis is running: `docker-compose ps redis`
- Check celery_beat logs: `docker-compose logs celery_beat`
