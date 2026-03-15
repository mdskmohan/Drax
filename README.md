# 🏋️ Drax — AI Personal Fitness Coach on Telegram

> Lose weight, build strength, and transform your lifestyle — entirely through Telegram.

Drax is a fully open-source AI fitness coach powered by **Claude AI** that lives in your Telegram. It acts as your personal trainer, nutritionist, and accountability coach — all in one bot.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🍽️ **Meal Tracking** | Log meals in plain text — AI parses calories & macros automatically |
| 💧 **Hydration Tracking** | Track water intake with smart reminders throughout the day |
| 🏋️ **AI Workout Plans** | Personalized daily workouts with sets, reps, rest times & YouTube tutorials |
| 📊 **Progress Reports** | Weekly AI-generated reports with trend analysis |
| ⚖️ **Weight Logging** | Track your weight journey with visual progress bars |
| 💪 **Daily Motivation** | Personalized morning motivation at 5 AM before your gym session |
| 🤕 **Injury Recovery** | Pain-aware workout modifications powered by AI |
| 📋 **Daily Plans** | Full meal + workout plan delivered every morning |

## 🤖 AI Stack

| Task | Model |
|---|---|
| Coaching, workout plans, reports | Claude Sonnet (main reasoning) |
| Meal parsing, quick replies | Claude Haiku (fast & cheap) |
| Nutrition data | Nutritionix API |
| Exercise tutorials | YouTube Data API v3 |

## 🗓️ Daily Schedule

```
5:00 AM  → Morning motivation + full workout plan
6:00 AM  → Pre-gym pump-up (30 min before gym)
Every 2h → Water reminders (if behind target)
9:00 PM  → Evening check-in (workout done? calories? water?)
Sunday   → Full weekly progress report
```

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/drax.git
cd drax
```

### 2. Get your API keys
| Key | Where to get it |
|---|---|
| Telegram Bot Token | Message `@BotFather` on Telegram → `/newbot` |
| Anthropic API Key | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| Nutritionix (optional) | [developer.nutritionix.com](https://developer.nutritionix.com) |
| YouTube API (optional) | [Google Cloud Console](https://console.cloud.google.com) → YouTube Data API v3 |

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. Run locally (no server needed)
```bash
# Start PostgreSQL
docker-compose up db -d

# Install and run
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_polling.py
```

### 5. Send `/start` to your bot on Telegram

---

## 🏗️ Architecture

```
Telegram User
      │
      ▼
FastAPI Webhook / Polling
      │
      ▼
Bot Router (handlers)
      │
   ┌──┴────────────────────┐
   │                       │
Onboarding             Meal/Water/
Flow                   Workout/Progress
   │                       │
   └──────┬────────────────┘
          │
     AI Agents (Claude)
  ┌───────┼──────────────┐
  │       │              │
Fitness  Nutrition   Hydration
Coach    Agent       Agent
  │       │              │
Motivation Progress  Recovery
Agent     Agent      Agent
          │
     External APIs
   Nutritionix | YouTube
          │
     PostgreSQL + Redis
```

## 📁 Project Structure

```
drax/
├── app/
│   ├── agents/          # 6 AI agents (fitness, nutrition, hydration, motivation, progress, recovery)
│   ├── bot/
│   │   └── handlers/    # Telegram message handlers
│   ├── models/          # PostgreSQL models (users, meals, water, workouts, weight, reports)
│   ├── services/        # Claude API, Nutritionix, YouTube
│   ├── tasks/           # Celery scheduled tasks (morning plan, reminders, weekly report)
│   └── api/             # FastAPI webhook endpoint
├── docker-compose.yml
├── Dockerfile
└── run_polling.py       # Local development entry point
```

---

## ☁️ Deploy to Production

See [DEPLOY.md](DEPLOY.md) for step-by-step guides for:
- **Railway** (recommended — free tier, one-click deploy)
- **Render**
- **Fly.io**
- **VPS** (DigitalOcean / Hetzner)

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

Ideas for contributions:
- [ ] Food photo AI detection (LLaVA integration)
- [ ] Multi-language support
- [ ] Apple Health / Google Fit sync
- [ ] Custom meal plan templates
- [ ] Gym schedule integration
- [ ] BMI and body fat tracking

---

## 📄 License

MIT License — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

## ⭐ Support

If this project helps you, please give it a star! It helps others find it.

Built with ❤️ using [Claude AI](https://anthropic.com), [python-telegram-bot](https://python-telegram-bot.org/), and FastAPI.
