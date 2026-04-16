import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    base_url: str = os.getenv("BASE_URL")
    timeout_s: float = 30.0
    token: str = os.getenv("TOKEN")
    port: int = int(os.getenv("PORT", "2201"))
    redis_url: str = os.getenv("REDIS_URL", "")
    redis_key_prefix: str = os.getenv("REDIS_KEY_PREFIX", "ruzbot")
    redis_ttl_profile_s: int = int(os.getenv("REDIS_TTL_PROFILE_S", "1800"))
    redis_ttl_group_schedule_s: int = int(
        os.getenv("REDIS_TTL_GROUP_SCHEDULE_S", "3600")
    )
    redis_ttl_user_schedule_s: int = int(os.getenv("REDIS_TTL_USER_SCHEDULE_S", "300"))
    redis_ttl_message_s: int = int(os.getenv("REDIS_TTL_MESSAGE_S", "600"))
    default_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    bot_token: str = os.getenv("BOT_TOKEN")
    payment_url: str = os.getenv("PAYMENT_URL")


settings = Settings()
