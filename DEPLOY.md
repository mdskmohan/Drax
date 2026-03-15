# Drax Deployment Guide

## Hosting Options Comparison

| Platform | Cost | Difficulty | Best for |
|---|---|---|---|
| **Railway** | Free $5/mo credit | ⭐ Easiest | Recommended — includes Postgres + Redis |
| **Render** | Free tier | ⭐⭐ Easy | Good free option |
| **Fly.io** | Free tier | ⭐⭐ Easy | Docker-native |
| **VPS (Hetzner)** | €3.29/mo | ⭐⭐⭐ Manual | Best value, full control |

---

## Option 1: Railway (Recommended — Easiest)

Railway auto-detects Docker, provisions Postgres and Redis for free.

### Steps

1. **Push your code to GitHub first** (see GitHub section below)

2. **Go to [railway.app](https://railway.app)** → Sign up with GitHub

3. **New Project → Deploy from GitHub repo** → select your drax repo

4. **Add PostgreSQL:**
   - Click `+ New` → Database → PostgreSQL
   - Railway auto-sets `DATABASE_URL` in your environment

5. **Add Redis:**
   - Click `+ New` → Database → Redis
   - Railway auto-sets `REDIS_URL`

6. **Set environment variables** in Railway dashboard → Variables:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   ANTHROPIC_API_KEY=your_key
   TELEGRAM_WEBHOOK_URL=https://your-app.railway.app
   DATABASE_URL=<auto-set by Railway>
   REDIS_URL=<auto-set by Railway>
   ```

7. **Deploy** — Railway builds your Dockerfile automatically

8. **Add Celery worker service:**
   - New Service → GitHub repo (same repo)
   - Override start command: `celery -A app.tasks.celery_app worker --loglevel=info`

9. **Add Celery beat service:**
   - New Service → GitHub repo (same repo)
   - Override start command: `celery -A app.tasks.celery_app beat --loglevel=info`

10. Your bot is live! The webhook is set automatically on startup.

---

## Option 2: Render

1. Go to [render.com](https://render.com) → New Web Service → connect GitHub repo

2. Settings:
   - **Runtime**: Docker
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

3. Add **PostgreSQL** database (Render free tier)

4. Add **Redis** (Render free tier)

5. Set environment variables in Render dashboard

6. Add two separate Worker services for Celery worker and beat

> Note: Render free tier spins down after 15 min inactivity. Use a paid plan ($7/mo) for a bot that must always be on.

---

## Option 3: Fly.io

```bash
# Install flyctl
brew install flyctl

# Login
fly auth login

# Launch (auto-detects Dockerfile)
fly launch

# Set secrets
fly secrets set TELEGRAM_BOT_TOKEN=your_token
fly secrets set ANTHROPIC_API_KEY=your_key
fly secrets set TELEGRAM_WEBHOOK_URL=https://your-app.fly.dev

# Create Postgres
fly postgres create --name drax-db
fly postgres attach drax-db

# Create Redis
fly redis create

# Deploy
fly deploy
```

---

## Option 4: VPS (Hetzner CX22 — €3.29/mo, best value)

### 1. Get a server
- [Hetzner Cloud](https://hetzner.com/cloud) → CX22 (2 vCPU, 4GB RAM) → Ubuntu 24.04
- Note your server IP

### 2. Point a domain (optional but recommended for webhook)
- Add an A record: `drax.yourdomain.com → YOUR_SERVER_IP`

### 3. SSH and set up
```bash
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin nginx certbot python3-certbot-nginx

# Clone your repo
git clone https://github.com/YOUR_USERNAME/drax.git
cd drax

# Configure environment
cp .env.example .env
nano .env  # fill in your keys + set TELEGRAM_WEBHOOK_URL=https://drax.yourdomain.com

# Start everything
docker compose up -d
```

### 4. SSL certificate (required for webhook)
```bash
certbot --nginx -d drax.yourdomain.com
```

### 5. Nginx config
```nginx
server {
    server_name drax.yourdomain.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Switching from Polling to Webhook

Once hosted, set `TELEGRAM_WEBHOOK_URL` in your `.env`:
```
TELEGRAM_WEBHOOK_URL=https://your-domain.com
```

The app automatically registers the webhook on startup via:
```python
await application.bot.set_webhook(url=f"{settings.telegram_webhook_url}/webhook")
```

For local development, leave `TELEGRAM_WEBHOOK_URL` empty and use `python run_polling.py`.

---

## GitHub → Auto-Deploy Setup

On Railway/Render/Fly.io, every `git push` to `main` triggers a new deployment automatically.

```bash
git add .
git commit -m "feat: update workout timing"
git push origin main
# → Auto-deploys in ~2 minutes
```
