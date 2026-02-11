# Как вносить изменения в бота и заливать на сервер

Пошаговая инструкция: правки на компьютере → GitHub → обновление на сервере.

---

## Часть 1: Внести изменения на компьютере

1. Открой проект в Cursor (или любом редакторе): папка `D:\code\Ref_bot_tg-main`.

2. Редактируй нужные файлы:
   - Логика бота: `bot/handlers/` (start.py, admin.py, cabinet.py и т.д.)
   - Кнопки: `bot/keyboards/` (inline.py, reply.py)
   - База данных: `bot/database/` (models.py, crud.py)
   - Конфиг: `bot/config.py`
   - Тексты, механика: см. структуру в README.

3. Проверь локально (по желанию):
   ```powershell
   cd D:\code\Ref_bot_tg-main
   python -m bot.main
   ```
   Напиши боту в Telegram, убедись, что всё работает. Остановка: `Ctrl+C`.

4. Закоммить и отправить на GitHub:
   ```powershell
   cd D:\code\Ref_bot_tg-main
   git add .
   git status
   git commit -m "Краткое описание изменений"
   git push
   ```
   - `git add .` — добавляет все изменённые файлы.
   - `git status` — показывает, что будет в коммите (можно пропустить).
   - `git commit -m "..."` — фиксирует изменения с сообщением.
   - `git push` — отправляет коммиты в репозиторий https://github.com/lostyoninternet/Ref_bot_tg.

   Если при `git push` просят логин/пароль — используй **Personal Access Token** (GitHub → Settings → Developer settings → Personal access tokens) вместо пароля.

---

## Часть 2: Обновить бота на сервере

1. Подключись к серверу по SSH:
   ```bash
   ssh root@85.239.62.103
   ```
   (Подставь свой IP, если другой.)

2. Перейди в папку бота и подтяни изменения с GitHub:
   ```bash
   cd /opt/Ref_bot_tg
   git pull
   ```

3. Обнови зависимости (если менялся `requirements.txt`):
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Перезапусти бота:
   ```bash
   sudo systemctl restart refbot
   ```

5. Проверь, что бот запущен:
   ```bash
   sudo systemctl status refbot
   ```
   Должно быть: `Active: active (running)`.

   Дополнительно проверь в Telegram: напиши боту, убедись, что логика и кнопки работают как задумано.

---

## Краткая шпаргалка

**На компьютере (после правок):**
```powershell
cd D:\code\Ref_bot_tg-main
git add .
git commit -m "описание"
git push
```

**На сервере (после push):**
```bash
ssh root@85.239.62.103
cd /opt/Ref_bot_tg
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart refbot
sudo systemctl status refbot
```

---

## Важные моменты

- **Файл `.env`** на сервере не трогается при `git pull` (его нет в репозитории). Токен, ADMIN_IDS, CHANNEL_ID меняешь вручную на сервере через `nano /opt/Ref_bot_tg/.env` при необходимости.

- **База данных** (`referral_bot.db`) лежит на сервере в `/opt/Ref_bot_tg/`. При обновлении кода она не удаляется. Если в коде менялись модели (новые таблицы/поля), при первом запуске после обновления бот сам создаст недостающие таблицы (см. `bot/database/session.py`).

- Если **добавлялись новые зависимости** в `requirements.txt`, на сервере обязательно выполни:
  ```bash
  cd /opt/Ref_bot_tg
  source venv/bin/activate
  pip install -r requirements.txt
  sudo systemctl restart refbot
  ```

- **Логи на сервере** (если что-то пошло не так):
  ```bash
  sudo journalctl -u refbot -f
  ```
  Выход: `Ctrl+C`.

---

## Если что-то пошло не так

| Проблема | Что сделать |
|----------|-------------|
| `git push` просит логин/пароль | Использовать Personal Access Token с GitHub. |
| На сервере `git pull` — конфликты | Не редактируй файлы на сервере. Все правки делай локально, потом `git add`, `commit`, `push` и снова `git pull` на сервере. При конфликтах можно сбросить папку к версии с GitHub: `cd /opt/Ref_bot_tg && git fetch && git reset --hard origin/main` (локальные правки на сервере пропадут). |
| После обновления бот не стартует | `sudo journalctl -u refbot -n 50` — посмотреть ошибки; проверить, что не меняли `.env` и не сломали синтаксис в коде. |
| Бот не реагирует в Telegram | `sudo systemctl status refbot` — активен ли; проверить токен в `.env` на сервере. |

Готово. После этого цикла (правки → commit → push → на сервере pull + restart) ты всегда сможешь вносить изменения в бота и заливать их на работающий сервер.
