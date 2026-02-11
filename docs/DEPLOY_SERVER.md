# Развёртывание бота на сервере Ubuntu (Timeweb)

Пошаговая инструкция: клонирование с GitHub и постоянный запуск.

---

## 1. Подключиться к серверу

С твоего компьютера (PowerShell или PuTTY):

```bash
ssh root@IP_АДРЕС_СЕРВЕРА
```

IP и пароль — в панели Timeweb. При первом входе подтверди подключение (`yes`).

---

## 2. Обновить систему и поставить Python

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git
python3 --version
```

Должна быть версия 3.8 или выше.

---

## 3. Клонировать репозиторий с GitHub

```bash
cd /opt
sudo git clone https://github.com/lostyoninternet/Ref_bot_tg.git
sudo chown -R $USER:$USER Ref_bot_tg
cd Ref_bot_tg
```

---

## 4. Создать виртуальное окружение и установить зависимости

```bash
cd /opt/Ref_bot_tg
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Проверка: `pip list` — должны быть aiogram, aiosqlite и т.д.

---

## 5. Создать файл .env

Файл `.env` в репозитории нет — его создаёшь только на сервере.

```bash
nano .env
```

Вставь (подставь свои данные):

```
BOT_TOKEN=твой_токен_от_BotFather
ADMIN_IDS=[550585948, 7702889726]
CHANNEL_ID=-1003374620893
BOT_USERNAME=Alabuga_Politech_referal_bot
REGISTRATION_URL=https://polytech.alabuga.ru/
```

Сохранить: `Ctrl+O`, Enter, выход: `Ctrl+X`.

---

## 6. Проверить запуск вручную

```bash
cd /opt/Ref_bot_tg
source venv/bin/activate
python -m bot.main
```

В Telegram напиши боту — должен отвечать. Остановка: `Ctrl+C`.

---

## 7. Настроить автозапуск (systemd)

Бот будет работать постоянно и перезапускаться после перезагрузки сервера.

Создать файл сервиса:

```bash
sudo nano /etc/systemd/system/refbot.service
```

Вставить (путь `/opt/Ref_bot_tg` — если клонировал в другое место, измени):

```ini
[Unit]
Description=Referral Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Ref_bot_tg
Environment=PATH=/opt/Ref_bot_tg/venv/bin
ExecStart=/opt/Ref_bot_tg/venv/bin/python -m bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохранить: `Ctrl+O`, Enter, `Ctrl+X`.

Включить и запустить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable refbot
sudo systemctl start refbot
sudo systemctl status refbot
```

В `status` должно быть `active (running)` зелёным.

---

## 8. Полезные команды

| Действие | Команда |
|----------|--------|
| Смотреть логи в реальном времени | `sudo journalctl -u refbot -f` |
| Остановить бота | `sudo systemctl stop refbot` |
| Запустить бота | `sudo systemctl start refbot` |
| Перезапустить бота | `sudo systemctl restart refbot` |
| Статус | `sudo systemctl status refbot` |

Выход из логов: `Ctrl+C`.

---

## 9. Обновление бота после изменений на GitHub

На своём компьютере: делаешь правки, потом `git add .`, `git commit -m "..."`, `git push`.

На сервере:

```bash
cd /opt/Ref_bot_tg
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart refbot
```

Проверить: `sudo systemctl status refbot` или написать боту в Telegram.

---

## Краткий чек-лист

1. `ssh root@IP`
2. `apt update && apt install python3 python3-venv git`
3. `cd /opt && git clone https://github.com/lostyoninternet/Ref_bot_tg.git`
4. `cd Ref_bot_tg && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
5. `nano .env` — вписать BOT_TOKEN, ADMIN_IDS, CHANNEL_ID и т.д.
6. Проверка: `python -m bot.main` → остановить `Ctrl+C`
7. `sudo nano /etc/systemd/system/refbot.service` — вставить конфиг выше
8. `sudo systemctl enable refbot && sudo systemctl start refbot && sudo systemctl status refbot`

После этого бот работает постоянно.
