# Робот-напоминатель в TELEGRAM

Скрипт на Python.
Запускается каждый час и проверяет, соответствует ли время его запуска cron-выражению из настроек.
Если соответствует, то берет сообщение из соответствующего блока настроек и отправляет его в чат телеграм.
Настройки описаны в json файле settings.json

```json
{
    "globals": {
        "timezone": "Europe/Moscow"
    },
    "schedules": [
        {
            "cron": "0 * 3 * *",
            "message": "Это сообщение отправляется каждый час 3 числа."
        },
        {
            "cron": "0 10 28 * *",
            "message": "Это сообщение отправляется 28 числа день в 10 часов."
        }
    ]
}
```

Для отправки сообщений в телеграм чат требуются токен телеграм бота и id чата. Они хранятся в файле .env

```sh
TELEGRAM_TOKEN=72863000056:SHGHD-HyPJ6YxxxxxxxxMqOhWoSwC1umJX3MO0
TELEGRAM_CHAT_ID=987xxx9879
```

Для обслуживания расписания, скриптом `palmface.sh` запускается веб-интерфейс `http://localhost:7878` таблицы расписания (sqlite).


## Запуск в проде

Создать файл службы `cron-telegram-reminder` для `systemd`

```sh
sudo nano /etc/systemd/system/cron-telegram-reminder.service
```
вставить туда, заменив USER и WORKDIR на правильные значения

```
[Unit]
Description=Cron Telegram Reminder App
After=network.target

[Service]
User=USER
Group=USER
WorkingDirectory=WORKDIR
ExecStart=WORKDIR/palmface.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

обновить все службы, разрешить запуск службы `cron-telegram-reminder` при перезагрузке, запустить службу `cron-telegram-reminder`

```sh
sudo systemctl daemon-reload
sudo systemctl enable cron-telegram-reminder
sudo systemctl start cron-telegram-reminder
sudo systemctl status cron-telegram-reminder
```
