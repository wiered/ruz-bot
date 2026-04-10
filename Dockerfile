# Сборка: docker build -t ruzbot .
# С ruz-client с ветки dev: docker build --build-arg RUZ_EXTRA=ruzclientdev -t ruzbot .
# Запуск: docker run --rm --env-file .env ruzbot
# Нужны переменные окружения: BOT_TOKEN, BASE_URL и при необходимости TOKEN, PORT, PAYMENT_URL (см. settings.py).

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml .
COPY src ./src

ARG RUZ_EXTRA=ruzclient
RUN pip install --upgrade pip \
    && pip install ".[${RUZ_EXTRA}]" \
    && rm -rf /src \
    && apt-get purge -y git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --uid 1000 bot
USER bot
WORKDIR /app

CMD ["python", "-m", "ruzbot"]
