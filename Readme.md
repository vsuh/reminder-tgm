# Telegram Cron Reminder

Этот проект представляет собой простое приложение для отправки напоминаний в Telegram на основе расписания `cron` и дополнительных модификаторов.

## Возможности

**Гибкое расписание:** Поддержка `cron` выражений и дополнительных модификаторов для точной настройки времени отправки напоминаний.
**Модификаторы:** Расширенные модификаторы d/n (каждые n дней) и w/n (каждые n недель) с поддержкой начальной даты (YYYYMMDD>).
**Веб-интерфейс:** Удобный веб-интерфейс для управления расписаниями, добавления, редактирования и удаления напоминаний.
**Экспорт/импорт расписаний:** Возможность экспорта и импорта расписаний в формате JSON.
**Запуск как сервис:** Поддержка запуска приложения как сервиса systemd в Linux.

## Установка и запуск
### Зависимости

[Список зависимостей](requirements.txt)

### Установка

- Клонируйте репозиторий:

```sh
git clone https://github.com/ваш_репозиторий/cron-reminder.git
```

- Создайте виртуальное окружение и установите зависимости:

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- Настройте переменные окружения (токен бота, ID чата и т.д.) в файле env/.env.prod (Linux) или env/.env.dev (Windows).  
Пример файла .env:

```ini
TELEGRAM_TOKEN=ваш_токен
TELEGRAM_CHAT_ID=ваш_id_чата
reminderTZ=Europe/Moscow
DB_PATH=settings.db
LOGPATH=log
LOG_LEVEL=INFO
PORT=7878
SECRET_KEY=ваш_секретный_ключ
```

### Запуск сервера расписаний

#### Разработка

```sh
./palmface.sh
```

### Продакшн (Linux)

- Создайте файл службы systemd:

```sh
sudo nano /etc/systemd/system/cron-telegram-reminder.service
```

Вставьте следующее содержимое, заменив USER и WORKDIR на ваши значения:

```ini
[Unit]
Description=Cron Telegram Reminder App
After=network.target

[Service]
User=USER
WorkingDirectory=WORKDIR
ExecStart=/usr/bin/python3 WORKDIR/run.py # Use full path to python3
Restart=always

[Install]
WantedBy=multi-user.target
```

- Обновите systemd, включите и запустите службу:

```sh
sudo systemctl daemon-reload
sudo systemctl enable cron-telegram-reminder
sudo systemctl start cron-telegram-reminder
sudo systemctl status cron-telegram-reminder
```

### Использование

#### Веб-интерфейс

Доступ к веб-интерфейсу осуществляется по адресу http://localhost:7878. Вы можете добавлять, редактировать и удалять расписания через веб-интерфейс.

#### API

Приложение предоставляет [REST API для управления расписаниями](API.md).

#### Модификаторы

Модификаторы позволяют уточнить время срабатывания `cron` выражения. Поддерживаются следующие модификаторы:

- d/n: Срабатывает каждые n дней.
- w/n: Срабатывает каждые n недель.
- YYYYMMDD>: Указывает начальную дату для отсчета. Например, 20240301>d/3 будет срабатывать каждые 3 дня, начиная с 1 марта 2024 года.

#### Пример импорта данных

```sh
curl -X POST -H "Content-Type: application/json;charset=utf-8" --data-binary @dataschedules.json http://localhost:7878/schedules_all
```
