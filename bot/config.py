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
    
    # Ключ шифрования PII (32 байта). Задай 64 hex-символа или строку ≥32 символов
    ENCRYPTION_KEY: str = ""
    
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

    @property
    def encryption_key_bytes(self) -> bytes:
        """32 байта для AES-256. Из ENCRYPTION_KEY: hex (64 символа) или строка UTF-8."""
        raw = (self.ENCRYPTION_KEY or "").strip()
        if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
            return bytes.fromhex(raw)
        b = raw.encode("utf-8")
        while len(b) < 32:
            b = b + b
        return b[:32]
    
    def get_referral_link(
        self,
        token_medium: Optional[str] = None,
        token_campaign: Optional[str] = None,
        token_content: Optional[str] = None,
    ) -> str:
        """
        Генерирует UTM-ссылку для реферала (в UTM — короткие токены: ник, почта, телефон).
        utm_source=referal, utm_medium=токен_ника, utm_campaign=токен_почты, utm_content=токен_номера
        """
        base = self.REGISTRATION_URL.rstrip("/")
        sep = "&" if "?" in base else "?"
        parts = [
            "utm_source=referal",
            f"utm_medium={quote((token_medium or '').strip())}",
            f"utm_campaign={quote((token_campaign or '').strip())}",
            f"utm_content={quote((token_content or '').strip())}",
        ]
        return base + sep + "&".join(parts)

    def get_application_utm_url(self) -> str:
        """
        Ссылка «оставить заявку на очный этап» для неподписанных пользователей.
        utm_source=hr, utm_medium=ref_bot, utm_campaign=tg_bot, utm_content=start
        """
        base = (self.REGISTRATION_URL or "").rstrip("/")
        sep = "&" if "?" in base else "?"
        parts = [
            "utm_source=hr",
            "utm_medium=ref_bot",
            "utm_campaign=tg_bot",
            "utm_content=start",
        ]
        return base + sep + "&".join(parts)


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
