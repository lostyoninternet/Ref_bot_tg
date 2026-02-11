from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
from urllib.parse import quote

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []
    CHANNEL_ID: int  # Закрытый канал удержания
    BOT_USERNAME: str = "RefBot"
    DATABASE_URL: str = "sqlite+aiosqlite:///./referral_bot.db"
    
    # URL сайта для регистрации на очный этап
    REGISTRATION_URL: str = "https://example.com/register"

    @field_validator('ADMIN_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        """Parse ADMIN_IDS from comma-separated string or single int."""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def admin_ids_list(self) -> List[int]:
        return self.ADMIN_IDS
    
    def get_referral_link(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> str:
        """
        Генерирует UTM-ссылку для реферала:
        utm_source=referal, utm_medium=ник_тг, utm_campaign=почта, utm_content=номер
        """
        base = self.REGISTRATION_URL.rstrip("/")
        sep = "&" if "?" in base else "?"
        parts = [
            "utm_source=referal",
            f"utm_medium={quote((username or '').strip())}",
            f"utm_campaign={quote((email or '').strip())}",
            f"utm_content={quote((phone or '').strip())}",
        ]
        return base + sep + "&".join(parts)


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
