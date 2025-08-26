# RuzMSTUCA Bot
Бот-помощник для просмотра расписания МГТУ ГА

## Docker build
If you want to run this with docker:

1. Clone repo
```bash
git clone https://github.com/wiered/ruz-bot.git
```

2. Cd to ruz-bot folder
```bash
cd ruz-bot
```

3. Run your own MongoDB localy or host it somewhere

    Guide: https://www.mongodb.com/

4. Create .env and add BOT_TOKEN, ADMIN_ID and MONGODB_ADRESS

    The file should look like this
```.env
BOT_TOKEN=your-bot-token-here
POSTGRESQL_URL=postgresql_uri
DOUPDATE=1 # 1 if want update on start 0 else
TIMER_HOUR=4
TIMER_MINUTE=31
```

5. Build Docker image
```bash
docker build -t ruz-bot .
```

6. Run Docker image
```bash
docker run ruz-bot
```

