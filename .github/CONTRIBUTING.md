# Contributing to Drax

Thank you for contributing! Here's how to get started.

## Setup for Development

```bash
git clone https://github.com/YOUR_USERNAME/drax.git
cd drax
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
docker-compose up db -d
python run_polling.py
```

## How to Contribute

1. **Fork** the repo
2. **Create a branch**: `git checkout -b feature/your-feature`
3. **Make changes** and test locally
4. **Commit**: `git commit -m "feat: describe your change"`
5. **Push**: `git push origin feature/your-feature`
6. **Open a Pull Request**

## Commit Style

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` code change with no feature/fix

## Adding a New Agent

1. Create `app/agents/your_agent.py` extending `BaseAgent`
2. Add to `app/agents/__init__.py`
3. Wire up handlers in `app/bot/handlers/`
4. Add commands to `app/bot/bot.py`

## Reporting Bugs

Open an issue with:
- What happened
- What you expected
- Steps to reproduce
- Your Python version and OS
