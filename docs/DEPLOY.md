# Деплой бота на сервер — пошаговый гайд

## Если потом планируешь перенос в корпоративный контур

**Проще всего переносить вариант на VPS (Linux + systemd).** Почему:

- В корпорации обычно свои серверы (Linux), внешние PaaS (Railway, Render) часто недоступны или запрещены.
- На VPS ты уже делаешь то же, что потом будет в контуре: сервер, Python, venv, systemd (или Docker). Перенос = те же шаги на другом хосте или тот же образ/конфиг.
- С PaaS при переносе придётся заново настраивать всё под внутреннюю инфраструктуру; с VPS — копируешь проект, .env, ставишь службу по той же инструкции.

**Рекомендация:** деплой по **Варианту A (VPS)** ниже. Если в контуре используют Docker — добавь Dockerfile (см. конец гайда) и переноси уже образ/комpose.

---

Есть два варианта: **VPS** (удобно для переноса в корп. контур) и **PaaS** (быстрый старт, но перенос в контур сложнее).

---

## Вариант A: VPS (Ubuntu/Debian) — предпочтительно для переноса в контур

Подойдёт для недорогого хостинга (от ~200–300 ₽/мес) и для последующего переноса на корпоративные серверы.

### Шаг 1. Арендовать VPS

- **Timeweb Cloud**, **Selectel**, **REG.RU**, **DigitalOcean**, **Hetzner** — любой сервер с Ubuntu 22.04 или Debian 12.
- Минимум: 1 ядро, 512 MB RAM (для бота хватит).
- При создании укажи **SSH-ключ** или запомни пароль root.

### Шаг 2. Подключиться по SSH

С своего компьютера:

```bash
ssh root@IP_АДРЕС_СЕРВЕРА
```

(или `ssh ubuntu@IP`, если создан пользователь `ubuntu`). Подставь свой IP.

### Шаг 3. Обновить систему и поставить Python

```bash
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip git
```

Проверка: `python3.11 --version` — должна быть 3.11 или выше.

### Шаг 4. Создать пользователя для бота (рекомендуется)

```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

Дальше команды — от имени `botuser` (или оставь root, если сервер только под бота).

### Шаг 5. Загрузить проект на сервер

**Способ 1 — через Git (если проект в репозитории):**

```bash
cd ~
git clone https://github.com/ТВОЙ_ЛОГИН/Ref_bor_tg.git
cd Ref_bor_tg
```

**Способ 2 — через SCP с твоего ПК (если репозитория нет):**

На **своём компьютере** (в папке с проектом, где лежит папка `bot`):

```bash
scp -r bot requirements.txt .env.example botuser@IP_СЕРВЕРА:~/Ref_bor_tg/
```

Потом на сервере:

```bash
cd ~/Ref_bor_tg
```

Важно: файл **`.env`** с реальными токенами нужно создать уже на сервере (см. шаг 6). На ПК не загружай `.env` по SCP, если в нём секреты.

### Шаг 6. Создать виртуальное окружение и зависимости

На сервере:

```bash
cd ~/Ref_bor_tg
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 7. Создать файл .env на сервере

```bash
nano .env
```

Вставь (подставь свои значения):

```
BOT_TOKEN=твой_токен_от_BotFather
ADMIN_IDS=твой_telegram_id
CHANNEL_ID=-1001234567890
BOT_USERNAME=имя_бота_без_собаки
REGISTRATION_URL=https://polytech.alabuga.ru/
```

Сохранить: `Ctrl+O`, Enter, выход: `Ctrl+X`.

Проверка запуска:

```bash
source venv/bin/activate
python -m bot.main
```

В Telegram бот должен ответить. Остановка: `Ctrl+C`.

### Вариант A2: VPS + Docker (собрать и запустить на сервере)

Если хочешь на VPS использовать именно Docker:

1. **Код на сервер попадает так же** — через Git или SCP (см. шаги 1–4 и шаг 5 выше). То есть ты загружаешь папку проекта (с `bot/`, `requirements.txt`, `Dockerfile`), а не «через Docker».
2. **Docker ставишь и запускаешь уже на VPS** — там же, на сервере, собираешь образ и поднимаешь контейнер.

Пошагово:

**На VPS после загрузки проекта (шаг 5):**

```bash
# Установка Docker (Ubuntu/Debian)
sudo apt update && sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io
# Опционально: Docker Compose
sudo apt install -y docker-compose-plugin
```

**Создать `.env` на сервере** (в папке проекта, как в шаге 7).

**Собрать образ и запустить контейнер** (в папке `~/Ref_bor_tg` или куда положил проект):

```bash
cd ~/Ref_bor_tg
sudo docker build -t referral-bot .
sudo docker run -d --name referral-bot --restart unless-stopped --env-file .env referral-bot
```

Проверка: `sudo docker logs -f referral-bot`. Остановка: `sudo docker stop referral-bot`. Запуск снова: `sudo docker start referral-bot`.

**Обновление бота (после git pull или загрузки новых файлов):**

```bash
cd ~/Ref_bor_tg
sudo docker stop referral-bot && sudo docker rm referral-bot
sudo docker build -t referral-bot .
sudo docker run -d --name referral-bot --restart unless-stopped --env-file .env referral-bot
```

**База SQLite:** по умолчанию она создаётся внутри контейнера и пропадёт при удалении контейнера. Чтобы данные сохранялись между перезапусками контейнера, создай каталог и смонтируй его, передав в `.env` путь к БД или добавь переменную в команду:

```bash
mkdir -p ~/Ref_bor_tg/data
sudo docker run -d --name referral-bot --restart unless-stopped --env-file .env \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="sqlite+aiosqlite:////app/data/referral_bot.db" \
  referral-bot
```

(В `.env` на сервере можно вместо этого задать `DATABASE_URL=sqlite+aiosqlite:////app/data/referral_bot.db` и тогда при запуске контейнера указывай только `-v $(pwd)/data:/app/data`.)

Итого: **сначала загружаешь проект на VPS (git/scp), потом на самом сервере ставишь Docker и там собираешь и запускаешь контейнер.** Не нужно собирать образ у себя на ПК и «загружать» его на VPS (так делают только через registry в более сложных сценариях).

---

### Шаг 8. Запускать бота как службу (systemd), чтобы работал всегда

Выйди из виртуального окружения (`deactivate`). Создай файл службы:

```bash
sudo nano /etc/systemd/system/referral-bot.service
```

Вставь (замени `botuser` и путь на свои):

```ini
[Unit]
Description=Referral Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/Ref_bor_tg
Environment=PATH=/home/botuser/Ref_bor_tg/venv/bin
ExecStart=/home/botuser/Ref_bor_tg/venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Сохрани и закрой редактор.

Включи и запусти службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable referral-bot
sudo systemctl start referral-bot
sudo systemctl status referral-bot
```

Должно быть `active (running)`. Логи:

```bash
sudo journalctl -u referral-bot -f
```

Перезапуск бота после изменений:

```bash
sudo systemctl restart referral-bot
```

---

## Вариант B: PaaS (Railway / Render)

Удобно, если не хочешь возиться с сервером. Есть бесплатные тарифы (лимиты по часам/трафику).

### Railway

1. Зайди на [railway.app](https://railway.app), войди через GitHub.
2. **New Project** → **Deploy from GitHub repo** → выбери репозиторий с ботом (или залей код в репо).
3. В настройках сервиса:
   - **Root Directory**: оставь пустым или укажи папку, где лежат `bot/` и `requirements.txt`.
   - **Build Command**: `pip install -r requirements.txt` (или оставь авто).
   - **Start Command**: `python -m bot.main`.
4. **Variables** — добавь переменные окружения (аналог `.env`):
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `CHANNEL_ID`
   - `BOT_USERNAME`
   - `REGISTRATION_URL`
5. **Deploy** — Railway сам соберёт и запустит. В логах смотри, что бот стартовал без ошибок.

### Render

1. [render.com](https://render.com) → **New** → **Background Worker**.
2. Подключи репозиторий с ботом.
3. **Build**: `pip install -r requirements.txt`, **Start**: `python -m bot.main`.
4. В **Environment** добавь те же переменные, что и для Railway.
5. Сохрани — Render развернёт воркер. Бот будет работать, пока не уснёт бесплатный инстанс (на free tier его могут останавливать при простое).

---

## Общие моменты

### Безопасность

- Файл **`.env`** не коммить в Git. Добавь в `.gitignore`:  
  `.env`
- На VPS лучше отключить вход по паролю и пользоваться только SSH-ключом.
- Не свети токены и `ADMIN_IDS` в скриншотах и публичных местах.

### Обновление бота на VPS

Если код в Git:

```bash
cd ~/Ref_bor_tg
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart referral-bot
```

Если заливаешь файлы вручную — скопируй новые файлы и снова `sudo systemctl restart referral-bot`.

### База данных (SQLite)

- Файл `referral_bot.db` создаётся в рабочей директории бота (`WorkingDirectory` в systemd).
- Делай резервные копии: периодически копируй `~/Ref_bor_tg/referral_bot.db` на свой ПК (например через `scp`).

### Если бот падает

- На VPS смотри логи: `sudo journalctl -u referral-bot -n 100`.
- Проверь, что в `.env` все переменные заданы и без лишних пробелов.
- Убедись, что `ADMIN_IDS` — число или числа через запятую без кавычек в `.env`.

---

## Краткая шпаргалка (VPS)

| Действие        | Команда |
|-----------------|--------|
| Статус бота     | `sudo systemctl status referral-bot` |
| Запуск          | `sudo systemctl start referral-bot` |
| Остановка       | `sudo systemctl stop referral-bot` |
| Перезапуск      | `sudo systemctl restart referral-bot` |
| Логи в реальном времени | `sudo journalctl -u referral-bot -f` |
| Обновление кода | `cd ~/Ref_bor_tg && git pull && sudo systemctl restart referral-bot` |

---

## Перенос в корпоративный технологический контур

Если сначала поднимал бота на VPS по Варианту A, перенос в контур делается так:

1. **Код и конфиг** — тот же репозиторий или архив (без `.env`). В контуре создаёшь `.env` или передаёшь переменные так, как принято (секреты в vault, переменные в CI/деплое).
2. **Сервер** — внутренний Linux (RHEL, Ubuntu, Astra и т.п.). Шаги те же: Python 3.11+, venv, `pip install -r requirements.txt`, systemd-юнит как в гайде (пути подставить под внутренние).
3. **Сеть** — доступ сервера в интернет к API Telegram (часто через корпоративный proxy/firewall; при необходимости настраиваешь `HTTP_PROXY` для aiohttp/бота).
4. **База** — SQLite можно оставить; если в контуре принята только своя СУБД (PostgreSQL и т.д.), тогда нужно заменить движок в коде (например `DATABASE_URL` на PostgreSQL) — структура таблиц та же.

**Если в контуре используют Docker** — добавь в корень проекта `Dockerfile` (пример ниже) и при переносе собирай образ на внутреннем registry и запускай контейнер так, как принято в контуре (docker run / docker-compose / k8s).

### Пример Dockerfile (опционально)

Создай в корне проекта файл `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ ./bot/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "bot.main"]
```

Сборка и запуск локально (для проверки):

```bash
docker build -t referral-bot .
docker run --env-file .env referral-bot
```

В контуре переменные окружения обычно подаются через оркестратор или секреты, без файла `.env` в образе.
