# 🏋️ Drax — AI Personal Fitness Coach on Telegram

> Your personal trainer, nutritionist, and accountability coach — all inside Telegram.

Drax is a fully open-source AI fitness bot that tracks your meals, generates personalised workouts, logs your water intake, and delivers a complete daily plan every morning. It adapts to your progress, handles injuries, and keeps you accountable — all through a simple Telegram chat.

---

## Health Advisory

> **Drax provides general fitness and nutrition guidance only — not medical advice.**

Drax calculates your targets using internationally validated methods (Mifflin-St Jeor BMR formula, ACSM activity multipliers, WHO/AND calorie guidelines). These are appropriate starting points for healthy adults with general weight-loss goals.

**Consult a professional before using Drax if you:**
- Have a chronic health condition (diabetes, heart disease, hypertension, kidney disease, etc.)
- Are pregnant or breastfeeding
- Take medication that affects weight, metabolism, or exercise capacity
- Are recovering from surgery or injury
- Have a history of eating disorders
- Are under 18 years of age (parental guidance and paediatric medical advice recommended)

**Where to get professional support:**
- **Registered Dietitian (RD/RDN)** — clinical nutrition plans, eating disorders, medical conditions
- **Certified Personal Trainer (CPT / CSCS)** — safe, individualised exercise programming
- **Physiotherapist / Sports Medicine Doctor** — injury management and return-to-sport
- **GP / Doctor** — before starting any significant diet or exercise programme

---

## What Drax does every day

Drax works in the background and messages you automatically at times you choose:

```
Your morning time  → Motivation + full workout plan + daily meal suggestions
Your preworkout time → Pump-up message before you head to the gym
Every N hours      → Water reminders when you're falling behind (configurable)
Your evening time  → Check-in: calories, water, workout summary
Your chosen day    → Full weekly progress report with trend analysis
```

All times and days are **fully configurable** via `/notifications`. You set your schedule — Drax respects it.

---

## Features

| Feature | How to use |
|---|---|
| 🍽️ **Meal Tracking** | Type what you ate: `"had chicken rice and salad"` |
| 📷 **Food Photo AI** | Send a photo of your meal — AI detects food and estimates macros |
| 💧 **Hydration Tracking** | `"drank 500ml"` or tap `/water` → quick log buttons |
| 🏋️ **Personalised Workouts** | `/workout` — plan adapts to your equipment, level, and schedule |
| 🏠 **Equipment-Aware Plans** | `/equipment` — tell Drax what you have or send a gym photo |
| 📋 **Daily Plan** | `/plan` — full meal + workout plan in one message |
| ⚖️ **Weight Logging** | `/weight` — AI feedback + progress bar every time you log |
| 📊 **Progress Dashboard** | `/progress` — weight journey, calories, water, workout streak |
| 🎯 **Macro Tracking** | Every meal logs calories, protein, carbs, and fat |
| 📈 **Weekly Report** | `/report` — deep AI analysis of your week |
| 💪 **Motivation** | `/motivation` — personalised message when you need a push |
| 🤕 **Injury Support** | Tell Drax what hurts — workout gets modified around the injury |
| 📅 **Custom Gym Schedule** | Pick exact training days — Drax auto-detects rest days |
| 🔔 **Configurable Notifications** | `/notifications` — set your own time + days for everything |
| 🔄 **Health Sync** | `/sync` — connect Apple Health or Google Fit |
| 🌍 **Multi-language** | English, Hindi, Spanish, French, Arabic, German |

---

## Quick Start (5 minutes)

### Step 1 — Clone the repo

```bash
git clone https://github.com/mdskmohan/Drax.git
cd Drax
```

### Step 2 — Get your API keys

You need **at minimum** a Telegram Bot Token + one LLM key. Everything else is optional.

#### Telegram Bot Token (required)
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., `My Fitness Coach`) and a username (e.g., `mycoach_bot`)
4. BotFather replies with a token like `8335466070:AAHHJi4EL...` — copy it

#### LLM API Key (required — pick one)

| Provider | Monthly cost (personal use) | Where to get | Best for |
|---|---|---|---|
| **Claude (Anthropic)** | ~$1–5/month | [console.anthropic.com](https://console.anthropic.com) → API Keys | Best coaching quality |
| **DeepSeek** | ~$0.20–1/month | [platform.deepseek.com](https://platform.deepseek.com) → API Keys | Cheapest |
| **OpenAI** | ~$1–3/month | [platform.openai.com](https://platform.openai.com) → API keys | Widely known |

> **Recommendation:** Start with **DeepSeek** (cheapest, great quality) or **Claude** (best responses).

#### Optional add-ons

| Service | Why | Free tier | Where |
|---|---|---|---|
| Nutritionix | Accurate calorie + macro data | 500 calls/day | [developer.nutritionix.com](https://developer.nutritionix.com) |
| YouTube API | Exercise tutorial videos in workouts | 10,000 units/day | [Google Cloud Console](https://console.cloud.google.com) → YouTube Data API v3 |

> Without these, Drax still works — it estimates nutrition via LLM and generates workouts without video links.

### Step 3 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in the 3 required values:

```env
TELEGRAM_BOT_TOKEN=paste_your_bot_token_here

LLM_PROVIDER=claude                     # or: openai, deepseek
ANTHROPIC_API_KEY=paste_your_key_here   # only if LLM_PROVIDER=claude
# OPENAI_API_KEY=                       # only if LLM_PROVIDER=openai
# DEEPSEEK_API_KEY=                     # only if LLM_PROVIDER=deepseek
```

Everything else in `.env` has working defaults for local use.

### Step 4 — Start the bot

**With Docker (recommended — one command):**

```bash
docker compose up
```

This starts the bot, PostgreSQL, Redis, and Celery worker automatically.

**Without Docker:**

```bash
# Start only the database and redis
docker compose up db redis -d

# Set up Python environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the bot
python run_polling.py
```

### Step 5 — Open Telegram and send /start

1. Search for your bot by the username you chose in BotFather
2. Tap **Start** or send `/start`
3. Drax shows a health disclaimer and begins onboarding (about 2 minutes)
4. You're live — your first morning plan arrives at your configured time

---

## Onboarding Walkthrough

When a new user sends `/start`, Drax walks through a short setup to personalise everything. Here is every step:

```
/start
 │
 ├─ 1. Health disclaimer displayed
 │
 ├─ 2. Full name
 │       "What's your full name?"
 │
 ├─ 3. Age
 │       "How old are you?"
 │       (Under-18 advisory shown if applicable)
 │
 ├─ 4. Gender  [Male] [Female]
 │       Used for Mifflin-St Jeor BMR formula
 │
 ├─ 5. Height
 │       "What's your height? (e.g., 175cm or 5'10\")"
 │       Accepts: cm, feet/inches (5'11", 5ft 10in, 5 feet 10 inches)
 │
 ├─ 6. Current weight
 │       "What's your current weight? (e.g., 85kg or 187 lbs)"
 │       Accepts: kg or lbs — stored internally in kg
 │
 ├─ 7. Goal weight
 │       "What's your goal weight? (e.g., 75kg or 165 lbs)"
 │       Accepts: kg or lbs
 │
 ├─ 8. Timeline
 │       "In how many months? (e.g., 10)"
 │       → Warning shown if goal implies > 1.0 kg/week loss (unsafe)
 │       → Realistic timeline suggestion provided
 │
 ├─ 9. Diet preference
 │       [Omnivore] [Vegetarian] [Vegan] [Keto] [Paleo]
 │
 ├─ 10. Workout level
 │        [Beginner 0–1yr] [Intermediate 1–3yr] [Advanced 3+yr]
 │        Used for TDEE activity multiplier
 │
 ├─ 11. Gym days per week
 │        [2] [3] [4] [5] [6]
 │
 ├─ 12. Training schedule (multi-select)
 │        [Mon] [Tue] [Wed] [Thu] [Fri] [Sat] [Sun] → Done
 │        Exact days used for gym-day detection and rest-day planning
 │
 ├─ 13. Equipment setup
 │        [Full Gym] [Home Gym] [Bodyweight Only] [Send Photo]
 │        → If Full Gym or Home: toggle individual items (barbell, dumbbells, etc.)
 │        → If Photo: vision AI scans and detects equipment automatically
 │
 ├─ 14. Language
 │        [English] [Hindi] [Spanish] [French] [Arabic] [German]
 │
 └─ Setup Complete! Summary shown:
         ✅ Calorie target (TDEE − 500 kcal, min 1200/1500 floor)
         ✅ Macro targets (protein / carbs / fat in grams)
         ✅ Daily water target (35 ml/kg + workout bonus)
         ✅ Training schedule
         ✅ Equipment list
         ✅ Language preference
         ✅ Professional consultation advisory
```

**What gets calculated automatically:**
- **BMR** — Mifflin-St Jeor (1990): most accurate validated formula
- **TDEE** — BMR × activity factor (1.375 beginner / 1.55 intermediate / 1.725 advanced)
- **Calorie target** — TDEE − 500 kcal (safe ~0.45 kg/week loss), minimum 1200 kcal women / 1500 kcal men
- **Macros** — 35% protein / 35% carbs / 30% fat of daily calories
- **Water target** — 35 ml/kg body weight + 500 ml on workout days (2000–5000 ml range)

The bot is fully ready the moment onboarding completes. No further setup needed.

---

## All Commands

| Command | What it does |
|---|---|
| `/start` | First-time setup, or return to main menu if already set up |
| `/menu` | Show the main menu with all action buttons |
| `/plan` | Get today's full meal plan + workout in one message |
| `/workout` | Generate today's workout plan with YouTube tutorial links |
| `/meal` | Log a meal — select type, then describe food or send a photo |
| `/water` | Log water — tap quick amounts or type `"drank 750ml"` |
| `/weight` | Log your current weight, get AI trend feedback |
| `/progress` | View full progress dashboard (weight, calories, water, workouts) |
| `/report` | Generate a detailed AI weekly progress report on demand |
| `/motivation` | Get a personalised motivational message |
| `/equipment` | Update your gym equipment (select, toggle, or scan a photo) |
| `/notifications` | Configure when and which days you receive each notification |
| `/sync` | Connect Apple Health or Google Fit via webhook |
| `/help` | Show all commands |

### Just type naturally

You don't need to use commands for daily tracking. Just message the bot:

| What you type | What happens |
|---|---|
| `"had 2 eggs, toast, and OJ for breakfast"` | Logs as breakfast with full macro breakdown |
| `"chicken biryani for lunch, medium portion"` | Logs as lunch — understands Indian and regional foods |
| `"drank 1L of water"` | Logs 1000ml hydration |
| `"2 glasses of water"` | Logs 500ml hydration |
| `"I weigh 87.5 kg"` or `"193 lbs"` | Logs weight (kg or lbs accepted), shows progress bar and AI feedback |
| `"sharp pain in my left knee"` | AI assesses, modifies workout to avoid the affected area |
| `"motivate me"` or `"I need a push"` | Personalised motivational message |
| `"what's my plan for today?"` | Full daily plan |
| Anything else | Drax's AI figures out your intent |

You can also **send a photo of your food** — Drax uses vision AI to identify the items and estimate nutrition automatically.

---

## Notification Schedule

Drax sends you automatic messages throughout the day. Every notification is fully configurable:

| Notification | Default | What you can change |
|---|---|---|
| 🌅 Morning Plan | 05:00, every day | Time + which days |
| ⚡ Pre-Workout | 06:00, every day | Time + which days |
| 🌙 Evening Check-in | 21:00, every day | Time + which days |
| 💧 Water Reminders | 08:00–20:00, every 2h | Active hours + interval (1h/2h/3h/4h) |
| 📊 Weekly Report | Sunday 08:00 | Time + which day of the week |

**To configure:** Send `/notifications` or tap **Settings** in the main menu.

All times are in **your local timezone**. The default is `Asia/Kolkata` — change `timezone` in your user profile if needed. Drax works in any timezone.

---

## Third-party data flows

Three external services receive data when you use Drax:

| Service | What is sent |
|---|---|
| **Telegram** | All messages (unavoidable — it's a Telegram bot) |
| **LLM provider** (Claude / OpenAI / DeepSeek) | Meal descriptions, chat text sent for AI responses |
| **Nutritionix** (optional) | Food descriptions sent for calorie lookup |

You choose the LLM provider via `LLM_PROVIDER` in `.env`. Nutritionix is optional — without it, Drax estimates nutrition via the LLM instead.

---

## How much does it cost to run?

For personal use, the API costs are minimal:

| LLM call type | Frequency | Estimated cost |
|---|---|---|
| Meal parsing (fast model) | Every meal logged | ~$0.0001 per meal |
| Workout generation (main model, cached daily) | Once per day | ~$0.005–0.02 |
| Weekly report (main model) | Once per week | ~$0.01–0.05 |
| Intent classification (fast / rule-based) | Every message | ~$0.00001 |
| Motivation / weight feedback (fast model) | On demand | ~$0.0001 |
| **Total for personal use per month** | | **~$1–5/month** |

Nutritionix and YouTube are both free within their daily limits. Hosting on Railway free tier costs $0 until you exceed their $5/month credit.

---

## Deploy to Production

### Railway — Recommended (15 min, free to start)

Railway handles Docker, PostgreSQL, Redis, and SSL automatically.

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select your Drax repo
4. Click `+ New` → **Add PostgreSQL** (Railway sets `DATABASE_URL` automatically)
5. Click `+ New` → **Add Redis** (Railway sets `REDIS_URL` automatically)
6. Go to your service → **Variables** → add:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   LLM_PROVIDER=claude
   ANTHROPIC_API_KEY=your_key
   TELEGRAM_WEBHOOK_URL=https://your-app-name.railway.app
   SECRET_KEY=any_long_random_string
   ```
7. Railway builds and deploys. Your bot is live.
8. Add Celery worker: `+ New Service` → same repo → start command:
   `celery -A app.tasks.celery_app worker --loglevel=info`
9. Add Celery beat (scheduler): `+ New Service` → same repo → start command:
   `celery -A app.tasks.celery_app beat --loglevel=info`

Every `git push` to main auto-deploys all three services.

### VPS (Hetzner / DigitalOcean) — $3–5/month, full control

See [DEPLOY.md](DEPLOY.md) for complete step-by-step guides for Railway, Hetzner VPS, Render, and Fly.io.

---

## Architecture

```
Telegram Message
      │
      ▼
Bot Router (python-telegram-bot)
  ├── Command handlers (/workout, /meal, /water, etc.)
  ├── Photo handler (equipment detection → food photo fallback)
  ├── Callback router (all inline button presses)
  └── Text router (state-based → LangGraph)
      │
      ▼
LangGraph (supervisor + agent nodes)
  ├── Supervisor  → classifies intent (rule-based shortcuts + fast LLM)
  ├── log_meal    → NutritionAgent → parse + Nutritionix → save + feedback
  ├── log_water   → HydrationAgent → parse + save + hydration status
  ├── get_workout → FitnessCoachAgent → generate (cached 24h) + YouTube links
  ├── log_weight  → ProgressAgent → save + trend analysis + progress bar
  ├── get_progress → DB aggregation → dashboard
  ├── get_plan    → meal plan + workout (combined)
  ├── get_motivation → MotivationAgent → fast LLM
  ├── report_pain → RecoveryAgent → AI assessment + modified workout
  ├── general     → fast LLM conversational fallback
  └── chain_check → auto-nudge for water after meal logging
      │
      ▼
PostgreSQL (all user data + logs)

Celery + Redis (scheduled notifications)
  └── Runs every 30 min → checks your configured time in your timezone
```

### What actually calls the LLM (cost transparency)

| Task | LLM? | Model | Notes |
|---|---|---|---|
| Meal text parsing | ✅ | Fast (Haiku/mini) | Understands natural language food |
| Meal feedback | ✅ | Fast | 2–3 sentence response |
| Workout generation | ✅ | Main (Sonnet/4o) | Cached daily — only once per day |
| Weekly report | ✅ | Main | Deep analysis |
| Pain assessment | ✅ | Main | Safety-critical |
| Weight feedback | ✅ | Fast | Short personalised response |
| Morning motivation | ✅ | Fast | Quick pump-up |
| Intent classification | ✅ | Fast | Only for ambiguous inputs |
| Hydration tips/status | ❌ | None | Rule-based math + templates |
| Rest day message | ❌ | None | 4 pre-written rotations |
| Progress bar | ❌ | None | Pure calculation |
| Water amount parsing | ❌ | None | Regex: "500ml", "2 glasses" → ml |
| Height/weight parsing | ❌ | None | Regex: "5'10\"", "187 lbs" → cm/kg |

### Standards & Methodology

| Calculation | Method | Reference |
|---|---|---|
| BMR | Mifflin-St Jeor (1990) | Most accurate validated formula; ACSM-recommended |
| TDEE | BMR × 1.375 / 1.55 / 1.725 | Standard activity multipliers |
| Calorie deficit | 500 kcal/day | AND/WHO: safe for ~0.45 kg/week loss |
| Calorie floor | 1200 kcal (women), 1500 kcal (men) | Academy of Nutrition and Dietetics |
| Macros | 35% protein / 35% carbs / 30% fat | ACSM high-protein fat-loss split |
| Hydration | 35 ml/kg + 500 ml workout bonus | EFSA adequate intake; ACSM guidelines |
| Safe loss rate | 0.25–1.0 kg/week | WHO / Academy of Nutrition and Dietetics |

---

## Project Structure

```
drax/
├── app/
│   ├── agents/              # AI coaching agents
│   │   ├── base_agent.py    # Shared: user context, language support
│   │   ├── nutrition_agent.py
│   │   ├── fitness_coach.py
│   │   ├── hydration_agent.py
│   │   ├── motivation_agent.py
│   │   ├── progress_agent.py
│   │   └── recovery_agent.py
│   ├── graph/               # LangGraph orchestration
│   │   ├── state.py         # DraxState TypedDict
│   │   ├── supervisor.py    # Intent classification
│   │   ├── nodes.py         # All agent node functions
│   │   └── graph.py         # Graph assembly + edges
│   ├── bot/
│   │   ├── handlers/        # Telegram command + message handlers
│   │   ├── keyboards.py     # All inline keyboards
│   │   └── bot.py           # Handler registration + routing
│   ├── models/              # SQLAlchemy models (User, MealLog, etc.)
│   ├── services/            # LLM, Nutritionix, YouTube API clients
│   ├── tasks/               # Celery scheduled tasks
│   ├── api/                 # FastAPI health sync endpoint
│   ├── config.py            # Pydantic settings (from .env)
│   ├── database.py          # Async SQLAlchemy engine
│   └── main.py              # FastAPI app (webhook + sync API)
├── alembic/                 # Database migrations
├── docker-compose.yml       # One-command local setup
├── Dockerfile
├── run_polling.py           # Local development entry point
├── .env.example             # Annotated config template
├── DEPLOY.md                # Hosting guides
└── CONTRIBUTING.md          # How to contribute
```

---

## Contributing

PRs are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Ideas for future contributions:
- [ ] Meal plans by cuisine (Mediterranean, Indian, Japanese, etc.)
- [ ] Progressive overload tracking (auto-increment weights week-over-week)
- [ ] Heart rate zone training via health sync
- [ ] Export progress data to CSV

---

## License

MIT — free to use, fork, modify, and build on. See [LICENSE](LICENSE).

---

Built with Claude AI, LangGraph, python-telegram-bot, and FastAPI.
If this helps you, star the repo ⭐
