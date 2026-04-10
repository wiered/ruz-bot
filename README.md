# RuzMSTUCA Bot

Telegram-бот для просмотра расписания МГТУ через backend API RUZ.

Бот работает в режиме long polling, хранит профиль пользователя на backend-сервере и позволяет:

- выбрать группу и подгруппу;
- посмотреть расписание на сегодня, завтра и неделю;
- открыть профиль пользователя;
- посмотреть преподавателей и предметы, которые есть в расписании выбранной недели;
- перейти к расписанию конкретного преподавателя или предмета.

## Зависимости

### Ссылки на компоненты

- [ruz-server (backend API)](https://github.com/wiered/ruz-server) - сервер backend API RUZ;
- [ruz-client (Python-клиент)](https://github.com/wiered/ruz-client) - асинхронный Python-клиент для backend API RUZ;
- [pyTelegramBotAPI](https://pypi.org/project/pyTelegramBotAPI/) — асинхронный Python-клиент для Telegram Bot API;
- [python-dotenv](https://pypi.org/project/python-dotenv/) — управление переменными окружения из файла `.env`;

## Требования

- Python 3.10 или новее;
- `git` для установки зависимости `ruz-client` из GitHub;
- Telegram Bot Token;
- доступный backend API RUZ.

## Установка

Клонирование репозитория:

```bash
git clone https://github.com/wiered/ruz-bot.git
cd ruz-bot
```

Создание и активация виртуального окружения:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Установка проекта вместе с клиентом RUZ:

```bash
pip install -U pip
pip install -e ".[ruzclient]"
```

Если нужна dev-ветка `ruz-client`:

```bash
pip install -e ".[ruzclientdev]"
```

## Переменные окружения

Проект читает настройки из переменных окружения и из файла `.env`.

Пример `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
BASE_URL=https://your-ruz-backend.example
TOKEN=your_backend_api_token
PAYMENT_URL=https://example.com/donate
PORT=2201
```

Назначение переменных:

- `BOT_TOKEN` - токен Telegram-бота;
- `BASE_URL` - базовый URL backend API;
- `TOKEN` - API-ключ для backend-сервиса, если он требуется;
- `PAYMENT_URL` - необязательная ссылка, которая добавляется в конец сообщений;
- `PORT` - служебная переменная, в текущем режиме long polling не используется при запуске бота.

Важно: не храните рабочие токены и ключи в публичном репозитории.

## Запуск

Локальный запуск:

```bash
python -m ruzbot
```

При старте приложение:

1. загружает переменные окружения через `python-dotenv`;
2. проверяет доступность `api.telegram.org` через `getMe`;
3. регистрирует обработчики;
4. запускает long polling.

Если `BOT_TOKEN` не задан или Telegram API недоступен, процесс завершится с ошибкой.

## Docker

Сборка образа:

```bash
docker build -t ruzbot .
```

Сборка с `ruz-client` из ветки `dev`:

```bash
docker build --build-arg RUZ_EXTRA=ruzclientdev -t ruzbot .
```

Запуск контейнера:

```bash
docker run --rm --env-file .env ruzbot
```

## Как работает бот

Основной сценарий для пользователя:

1. Отправить `/start`.
2. Выбрать группу.
3. Ввести подгруппу: `0`, `1` или `2`.
4. Использовать кнопки меню для просмотра расписания.

Данные о пользователе, группе и подгруппе бот получает и обновляет через backend API.

## Ограничения текущей реализации

- Пункты "Преподаватели" и "Предметы" в главном меню сейчас ведут на временную заглушку.
- Списки преподавателей и предметов доступны из просмотра недели пользователя.
- Проект не содержит тестов и CI-конфигурации в этом репозитории.
- Для работы обязательно нужен совместимый backend API, одного Telegram токена недостаточно.

## Структура проекта

```text
src/ruzbot/
  __main__.py         Точка входа
  main.py             Запуск приложения и polling
  bot.py              Инициализация бота и /start
  callbacks.py        Маршрутизация callback и текстовых сообщений
  commands.py         Основные команды и форматирование расписания
  search_handlers.py  Поиск по преподавателям и дисциплинам
  settings.py         Загрузка конфигурации
  utils.py            Клиент RUZ и вспомогательные функции
```

## Лицензия

Проект распространяется под лицензией, указанной в файле [LICENSE](LICENSE).
