"""
Очистка базы данных бота.

Варианты:
  --full     Удалить файл referral_bot.db (полный сброс). Бот создаст БД заново при запуске.
  --data     Очистить только данные (пользователи, рефералы, UTM-токены, выдачи грейдов, рассылки).
             Грейды, контакты и настройки bot_settings сохраняются.

Запуск из корня проекта:
  python scripts/clear_db.py --full
  python scripts/clear_db.py --data
"""
import asyncio
import sys
from pathlib import Path

# Добавить корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from bot.database.session import engine, init_db
from bot.config import settings


async def clear_data_only():
    """Очистить таблицы с данными, сохранить грейды, контакты, настройки."""
    tables_order = [
        "grade_claims",  # FK на users и grades
        "referrals",     # FK на users
        "broadcasts",
        "utm_tokens",
        "users",
    ]
    async with engine.begin() as conn:
        for table in tables_order:
            await conn.execute(text(f"DELETE FROM {table}"))
    print("Данные очищены (users, referrals, utm_tokens, grade_claims, broadcasts). Грейды, контакты и настройки сохранены.")


async def full_reset():
    """Удалить файл БД. Путь берётся из DATABASE_URL (sqlite:///./referral_bot.db)."""
    url = settings.DATABASE_URL
    if "sqlite" not in url:
        print("Полный сброс поддерживается только для SQLite. Укажите DATABASE_URL с sqlite.")
        return
    # sqlite+aiosqlite:///./referral_bot.db -> referral_bot.db в текущей рабочей папке
    db_path = url.split("/")[-1].split("?")[0]
    if not db_path or db_path == "":
        db_path = "referral_bot.db"
    path = Path(db_path)
    if path.is_file():
        path.unlink()
        print(f"Файл {path.absolute()} удалён. При следующем запуске бот создаст пустую БД.")
    else:
        print(f"Файл {path.absolute()} не найден.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    arg = sys.argv[1].lower()
    if arg == "--full":
        asyncio.run(full_reset())
    elif arg == "--data":
        asyncio.run(clear_data_only())
    else:
        print("Использование: --full или --data")
        print(__doc__)


if __name__ == "__main__":
    main()
