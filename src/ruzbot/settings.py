import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    base_url: str = os.getenv("BASE_URL")
    timeout_s: float = 30.0
    token: str = os.getenv("TOKEN")
    port: int = int(os.getenv("PORT", "2201"))
    default_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    bot_token: str = os.getenv("BOT_TOKEN")
    payment_url: str = os.getenv("PAYMENT_URL")


settings = Settings()
