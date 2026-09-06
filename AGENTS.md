# Agent notes — ruz-bot

## Project Structure & Module Organization

- **Src layout:** package `src/ruzbot/` (`setuptools` `where = ["src"]` in `pyproject.toml`).
- **Entry:** `python -m ruzbot` → `__main__.py` → `main.main`.
- **Modules:** `main` (bootstrap, polling), `bot` (TeleBot, `/start`), `callbacks`, `commands`, `search_handlers`, `markups`, `settings` (dotenv), `utils` (RUZ client). `deathnote.py` = schedule formatting + small guardrails (used by `commands` / `search_handlers`).

## Build, Test, and Development Commands

- **Install:** venv → `pip install -e ".[ruzclient]"` or `".[ruzclientdev]"` for dev `ruz-client`.
- **Run bot:** `python -m ruzbot` + `.env` (see `README.md`). **Agents:** don’t start bot in sessions — token + duplicate polling risk.
- **Smoke:** `python -c "import ruzbot"` after install (no polling).
- **Docker:** `docker build -t ruzbot .` (optional `--build-arg RUZ_EXTRA=ruzclientdev`); `docker run --rm --env-file .env ruzbot`.
- **VS Code:** `tasks.json` has Docker + `python -m pytest`; pytest not in `pyproject.toml` — install manually until tests land.
- **Tests:** use local pytest `.\.venv\Scripts\pytest -q`

## Coding Style & Naming Conventions

- Python **≥3.10** (Docker 3.12). PEP 8: `snake_case` / `PascalCase`, imports `from ruzbot…`.
- User strings often Russian; match file’s comment language.
- Keep `pyTelegramBotAPI` pin; no formatter/linter in repo — follow neighbors, small diffs.

## Testing Guidelines

- No `tests/` or CI yet (per `README.md`).
- New tests: `pytest`, `tests/` + `test_*.py`; mock Telegram + RUZ HTTP; no real token/backend in unit suite.
- Full E2E = manual + Telegram + backend. Don’t use live bot as “test runner.”
