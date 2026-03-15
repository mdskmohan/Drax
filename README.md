# 🏋️ Drax — AI Personal Fitness Coach on Telegram

> Your personal trainer, nutritionist, and accountability coach — all inside Telegram.

Drax is a fully open-source AI fitness bot that tracks your meals, generates personalized workouts, logs your water intake, and delivers a complete daily plan every morning at 5 AM. It adapts to your progress, handles injuries, and keeps you accountable — all through a simple Telegram chat.

---

## What Drax does for you every day

```
5:00 AM  → Morning motivation + full workout plan sent to your Telegram
6:00 AM  → Pre-gym pump-up message (30 min before you leave)
Every 2h → Water reminders if you're falling behind
9:00 PM  → Evening check-in — did you eat well? did you work out? how's your water?
Sunday   → Full weekly progress report with trend analysis
```

You just show up — Drax handles the coaching.

---

## Features

| Feature | How to use it |
|---|---|
| 🍽️ **Meal Tracking** | Just type what you ate — `"had chicken rice and salad"` |
| 💧 **Hydration** | Log water with `"drank 500ml"` or `/water` |
| 🏋️ **Workout Plans** | `/workout` — personalized plan with YouTube tutorials |
| 📋 **Daily Plan** | `/plan` — full meal + workout plan for the day |
| ⚖️ **Weight Logging** | `/weight` — type your weight, get AI feedback + progress bar |
| 📊 **Progress** | `/progress` — dashboard with weight journey, calories, water, workouts |
| 📈 **Weekly Report** | `/report` — detailed AI analysis every Sunday |
| 💪 **Motivation** | `/motivation` — when you need a push |
| 🤕 **Injury Support** | Tell Drax what hurts — it modifies your workout around it |

---

## Quick Start (5 minutes)

### Step 1 — Clone the repo

```bash
git clone https://github.com/mdskmohan/Drax.git
cd Drax
```

### Step 2 — Get your API keys

You need **at minimum** a Telegram Bot Token + one LLM API key. Everything else is optional.

#### Required: Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My Fitness Coach") and a username (e.g., `myfitnesscoach_bot`)
4. BotFather will send you a token like `8335466070:AAHHJi4ELa8odxBP99zL6HyQ...` — copy it

#### Required: One LLM API Key (pick one)

| Provider | Cost | Where to get it | Best for |
|---|---|---|---|
| **Claude (Anthropic)** | ~$0.25/1M tokens (Haiku) | [console.anthropic.com](https://console.anthropic.com) → API Keys | Best quality, recommended |
| **DeepSeek** | ~$0.07/1M tokens | [platform.deepseek.com](https://platform.deepseek.com) → API Keys | Cheapest option |
| **OpenAI** | ~$0.15/1M tokens (4o-mini) | [platform.openai.com](https://platform.openai.com) → API keys | Widely available |

> **Recommendation:** Start with **DeepSeek** if you want the cheapest option, or **Claude** for the best coaching quality.

#### Optional: Nutritionix (accurate calorie/macro data)
- Free tier: 500 requests/day
- Sign up at [developer.nutritionix.com](https://developer.nutritionix.com)
- Without this, Drax estimates nutrition using the LLM — still works, just less precise

#### Optional: YouTube API (exercise tutorial videos)
- Free tier: 10,000 requests/day (plenty)
- Go to [Google Cloud Console](https://console.cloud.google.com) → Create project → Enable "YouTube Data API v3" → Credentials → API Key
- Without this, Drax generates workouts without video links

### Step 3 — Configure your environment

```bash
cp .env.example .env
```

Open `.env` and fill in your keys — it takes 2 minutes:

```env
TELEGRAM_BOT_TOKEN=paste_your_token_here

LLM_PROVIDER=claude                    # or: openai, deepseek
ANTHROPIC_API_KEY=paste_your_key_here  # only needed if LLM_PROVIDER=claude
# OPENAI_API_KEY=                      # only needed if LLM_PROVIDER=openai
# DEEPSEEK_API_KEY=                    # only needed if LLM_PROVIDER=deepseek
```

### Step 4 — Run locally

The easiest way is Docker (handles PostgreSQL and Redis automatically):

```bash
docker compose up
```

That's it. The bot starts in polling mode automatically.

Or without Docker:

```bash
# Start database
docker compose up db redis -d

# Install Python deps
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run
python run_polling.py
```

### Step 5 — Start the bot on Telegram

1. Open Telegram
2. Search for your bot by username (the one you set in BotFather)
3. Send `/start`
4. Complete the onboarding (takes ~2 minutes — sets your weight, goal, gym schedule, diet preferences)
5. You're live

---

## All Commands

| Command | What it does |
|---|---|
| `/start` | First-time setup / return to main menu |
| `/menu` | Show the main menu buttons |
| `/plan` | Get today's full meal + workout plan |
| `/workout` | Generate today's workout with YouTube links |
| `/meal` | Log a meal (select type → describe food) |
| `/water` | Log water intake (quick buttons or type amount) |
| `/weight` | Log your current weight |
| `/progress` | View your full progress dashboard |
| `/report` | Generate a detailed weekly progress report |
| `/motivation` | Get a personalized motivational message |
| `/help` | Show all commands |

### Free-text logging (just type naturally)

You don't have to use commands for everything. Just type:

- `"had 2 eggs and toast for breakfast"` → logs as breakfast
- `"drank 1L of water"` → logs water intake
- `"I weigh 87.5kg"` → logs weight
- `"I feel a sharp pain in my knee"` → Drax assesses and modifies your workout
- `"motivate me"` → get a motivation message
- Anything else → Drax's AI figures out what you need

---

## How much does it cost to run?

Running Drax for personal use costs almost nothing:

| What | Cost estimate |
|---|---|
| Claude Haiku (most calls) | ~$0.001–0.003 per day of active use |
| Claude Sonnet (workout/report gen) | ~$0.01–0.05 per workout plan |
| Nutritionix free tier | $0 (500 requests/day) |
| YouTube free tier | $0 (10,000 units/day) |
| **Total per month (personal use)** | **~$1–5/month in API costs** |

Hosting on Railway free tier = $0 extra until you exceed $5/month credit.

---

## Deploy to Production (always-on bot)

For 24/7 operation, you need to host it. The easiest option is **Railway**.

### Railway — Recommended (15 min setup, free to start)

Railway automatically handles Docker, PostgreSQL, Redis, and SSL.

1. Push your code to GitHub (already done if you forked)

2. Go to [railway.app](https://railway.app) → sign up with GitHub

3. Click **New Project** → **Deploy from GitHub repo** → select your Drax repo

4. Add PostgreSQL:
   - Click `+ New` → Database → **Add PostgreSQL**
   - Railway sets `DATABASE_URL` automatically

5. Add Redis:
   - Click `+ New` → Database → **Add Redis**
   - Railway sets `REDIS_URL` automatically

6. Set environment variables (Railway dashboard → your service → Variables):
   ```
   TELEGRAM_BOT_TOKEN=your_token
   LLM_PROVIDER=claude
   ANTHROPIC_API_KEY=your_key
   TELEGRAM_WEBHOOK_URL=https://your-app-name.railway.app
   SECRET_KEY=any_random_string_here
   ```

7. Railway builds and deploys automatically. Your bot is live.

8. Add Celery worker (for scheduled messages):
   - `+ New Service` → GitHub repo (same repo)
   - Set start command: `celery -A app.tasks.celery_app worker --loglevel=info`

9. Add Celery beat (scheduler):
   - `+ New Service` → GitHub repo (same repo)
   - Set start command: `celery -A app.tasks.celery_app beat --loglevel=info`

> Every `git push` to main now auto-deploys. Zero maintenance.

### VPS — Best value ($3–5/month, full control)

Best if you want full control or are running it for multiple users.

See [DEPLOY.md](DEPLOY.md) for step-by-step guides for Railway, VPS (Hetzner), Render, and Fly.io.

---

## Architecture

```
Telegram Message
      │
      ▼
Bot Router (python-telegram-bot)
      │
      ▼
LangGraph Supervisor
  (classifies intent: meal/water/workout/progress/etc.)
      │
      ▼
Agent Node (does the work)
  ├── log_meal   → NutritionAgent → parse + save + feedback
  ├── log_water  → HydrationAgent → parse + save + status
  ├── get_workout → FitnessCoachAgent → generate plan (cached daily)
  ├── log_weight → ProgressAgent → save + feedback
  ├── get_progress → DB queries → dashboard
  ├── get_plan   → meal plan + workout (parallel)
  ├── get_motivation → MotivationAgent → fast LLM
  ├── report_pain → RecoveryAgent → assess + modify workout
  └── general    → fast LLM fallback
      │
      ▼
Celery + Redis (scheduled tasks)
      │
PostgreSQL (all data stored)
```

### LLM Usage — What actually needs AI

Not everything calls the LLM. Here's what does and doesn't:

| Task | Uses LLM? | Why |
|---|---|---|
| Parse meal text | ✅ Fast model (Haiku/mini) | Needs to understand food descriptions |
| Generate workout plan | ✅ Main model (cached 24h) | Complex personalized planning |
| Weekly progress report | ✅ Main model | Deep analysis needed |
| Pain assessment | ✅ Main model | Safety-critical, needs reasoning |
| Weight/motivation feedback | ✅ Fast model | Short personal responses |
| Hydration status/tips | ❌ Rule-based | Just math + templates |
| Rest day message | ❌ Templates | Pre-written, rotated randomly |
| Progress bar | ❌ Math | Pure computation |
| Water amount parsing | ❌ Regex | "500ml", "2 glasses" → numbers |
| Intent classification | ✅ Fast (or rule-based) | Supervisor node + shortcuts |

---

## Project Structure

```
drax/
├── app/
│   ├── agents/          # 6 specialized agents (fitness, nutrition, hydration, motivation, progress, recovery)
│   ├── graph/           # LangGraph: state, supervisor, nodes, graph assembly
│   ├── bot/
│   │   └── handlers/    # Telegram command and message handlers
│   ├── models/          # PostgreSQL models
│   ├── services/        # LLM (Claude/OpenAI/DeepSeek), Nutritionix, YouTube
│   └── tasks/           # Celery scheduled tasks
├── docker-compose.yml   # One-command local setup
├── Dockerfile
├── run_polling.py       # Local development entry point
└── .env.example         # Template — copy to .env and fill in keys
```

---

## Contributing

PRs are welcome! See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

Ideas:
- [ ] Food photo AI detection
- [ ] Apple Health / Google Fit sync
- [ ] Multi-language support
- [ ] Macro targets (not just calories)
- [ ] Gym schedule / rest day detection

---

## License

MIT — free to use, fork, and build on.

---

Built with Claude AI, LangGraph, python-telegram-bot, and FastAPI.
If this helps you, star the repo ⭐ — it helps others find it.
