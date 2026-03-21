# Drax — Production Deployment Guide

## Which option should I pick?

| Platform | Monthly cost | Difficulty | Best for |
|---|---|---|---|
| **Railway** | Free → $5+ | ⭐ Easiest | **Recommended.** Auto-provisions Postgres + Redis, zero config |
| **Hetzner VPS** | €3.29–4.49 | ⭐⭐⭐ Manual | Best value for long-term hosting, full control |
| **Render** | Free → $7+ | ⭐⭐ Easy | Good free option but spins down on inactivity |
| **Fly.io** | Free → $5+ | ⭐⭐ Medium | Docker-native, global edge |

**Bottom line:**
- First time deploying? → **Railway**
- Want the cheapest long-term? → **Hetzner VPS**
- Free forever (but with cold starts)? → **Render free tier** (not great for a bot)

---

## Option 1: Railway (Recommended)

Railway detects your Dockerfile, provisions managed Postgres and Redis, gives you a public HTTPS URL, and auto-deploys on every `git push`. The free $5/month credit is usually enough for a personal-use bot.

### Step-by-step

**1. Push your code to GitHub**
```bash
git remote add origin https://github.com/YOUR_USERNAME/drax.git
git push -u origin main
```

**2. Sign up at [railway.app](https://railway.app)** with your GitHub account

**3. Create a new project**
- Click **New Project** → **Deploy from GitHub repo**
- Select your Drax repository
- Railway detects the Dockerfile and starts building

**4. Add PostgreSQL**
- In your project, click **+ New** → **Database** → **PostgreSQL**
- Railway automatically adds `DATABASE_URL` to your environment

**5. Add Redis**
- Click **+ New** → **Database** → **Redis**
- Railway automatically adds `REDIS_URL`

**6. Set environment variables**

Click on your web service → **Variables** tab → add these:

```
TELEGRAM_BOT_TOKEN=your_token_here
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your_key_here
TELEGRAM_WEBHOOK_URL=https://YOUR-APP-NAME.railway.app
SECRET_KEY=generate_any_random_string_here
DEBUG=false
```

Optional (for accurate nutrition and workout videos):
```
NUTRITIONIX_APP_ID=your_app_id
NUTRITIONIX_API_KEY=your_key
YOUTUBE_API_KEY=your_key
```

**7. Done.** Your bot is live. Every `git push` to main triggers an automatic redeploy.

> **No separate Celery services needed.** The asyncio scheduler runs inside the main process and handles all scheduled notifications (morning plan, water reminders, evening check-in, weekly report). A single Railway service is all you need.

### Railway costs

| What | Free credit |
|---|---|
| Web service (includes scheduler) | ~$0.50–1/month |
| PostgreSQL (1GB) | ~$1/month |
| Redis | ~$0.50/month |
| **Total** | **~$2–2.50/month** (well within $5 free credit) |

---

## Option 2: Hetzner VPS (Best value for long-term)

A Hetzner CX22 (2 vCPU, 4 GB RAM) at €3.29/month runs all 5 Docker services comfortably. This is the best long-term option — you own everything and have full control.

### Step-by-step

**1. Create a server**
- Go to [hetzner.com/cloud](https://hetzner.com/cloud) → New Server
- Select **CX22** (2 vCPU, 4 GB RAM) → **Ubuntu 24.04** → cheapest datacenter near you
- Add an SSH key for access
- Note the server IP address

**2. (Optional) Point a domain**

A domain is recommended because Telegram webhooks require HTTPS. You can get a free subdomain or use your own.

```
A record:  drax.yourdomain.com  →  YOUR_SERVER_IP
```

If you don't have a domain, use polling mode instead (set `TELEGRAM_WEBHOOK_URL=` blank).

**3. SSH into your server**
```bash
ssh root@YOUR_SERVER_IP
```

**4. Install Docker**
```bash
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin
```

**5. Clone your repo**
```bash
git clone https://github.com/YOUR_USERNAME/drax.git
cd drax
```

**6. Configure environment**
```bash
cp .env.example .env
nano .env
```

Fill in your keys. If you have a domain:
```
TELEGRAM_WEBHOOK_URL=https://drax.yourdomain.com
```

If no domain (polling mode):
```
TELEGRAM_WEBHOOK_URL=
```

**7. Start everything**
```bash
docker compose up -d
```

This starts 3 services: db, redis, web. The asyncio scheduler runs inside the web service — no separate Celery containers needed.

**8. SSL with Nginx (only needed if using webhook)**
```bash
apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
cat > /etc/nginx/sites-available/drax << 'EOF'
server {
    server_name drax.yourdomain.com;
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/drax /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Get SSL certificate (free via Let's Encrypt)
certbot --nginx -d drax.yourdomain.com
```

**9. Auto-restart on server reboot**
```bash
docker compose up -d --restart always
# Or set restart: always in docker-compose.yml (already done)
```

**Updating after code changes:**
```bash
cd drax
git pull
docker compose up -d --build
```

---

## Option 3: Render

**Pros:** Free tier available, simple UI
**Cons:** Free tier spins down after 15 min inactivity (bad for a bot that sends 5 AM messages)

**Use Render if:** You're willing to use a paid plan ($7/month for the web service).

1. Go to [render.com](https://render.com) → New Web Service → connect GitHub repo
2. Runtime: Docker
3. Add **PostgreSQL** database (free tier, 1GB)
4. Add **Redis** (free tier)
5. Set environment variables
6. Add two background worker services for Celery (worker + beat)

---

## Option 4: Fly.io

```bash
# Install
brew install flyctl
fly auth login

# Launch (auto-detects Dockerfile)
fly launch

# Create and attach PostgreSQL
fly postgres create --name drax-db
fly postgres attach drax-db

# Create Redis
fly redis create --name drax-redis

# Set secrets
fly secrets set TELEGRAM_BOT_TOKEN=your_token
fly secrets set ANTHROPIC_API_KEY=your_key
fly secrets set TELEGRAM_WEBHOOK_URL=https://your-app.fly.dev

# Deploy
fly deploy
```

For Celery worker and beat, create separate apps or use Fly Machines.

---

## Polling vs Webhook

| Mode | When to use | How |
|---|---|---|
| **Polling** | Local dev, no domain | Leave `TELEGRAM_WEBHOOK_URL` blank. Run `python run_polling.py` |
| **Webhook** | Production, hosted | Set `TELEGRAM_WEBHOOK_URL=https://your-domain.com`. The app registers it on startup |

On Railway/Render/Fly, use webhook mode — it's more efficient and reliable.

---

## After deploying — run the database migrations

```bash
# Railway: use the Railway shell in the dashboard
# VPS/Fly: SSH into the web container

alembic upgrade head
```

Or add this to your startup command in the Dockerfile/Procfile:
```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Monitoring

Check logs on Railway:
- Dashboard → your service → **Deployments** → **View Logs**

Check logs on VPS:
```bash
docker compose logs -f web
docker compose logs -f celery_worker
```

If scheduled notifications aren't firing (no 5 AM messages), check the web service logs — the asyncio scheduler runs inside the main process:
```bash
docker compose logs -f web
```
Look for lines like `[scheduler] morning_plan sent to user ...` or `[scheduler] next run in Xs`.
