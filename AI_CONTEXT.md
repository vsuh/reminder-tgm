# AI_CONTEXT — reminder-tgm

> Архитектура и постоянные ограничения. Обновлять редко. Текущее состояние — в `task.md`.

## Назначение
Персональные напоминания в Telegram и ntfy.sh по cron-выражениям + модификаторы (см. Readme.md).

## Репозитории и деплой
- Код: https://github.com/vsuh/reminder-tgm (ветка master, GitHub user `vsuh`)
- Прод: контейнер из https://github.com/vsuh/cron-tg-docker (`docker pull vsuh/cron-tg:latest`)
- Релиз: `git tag v1.1.z && git push origin master --tags` -> workflow notify-docker обновляет образ
- Исходники также в vault: `D:\Sync\AI.obsdn\10-projects\reminder-tgm` (копия, сверять с GitHub)

## Архитектура (два процесса)
- `web/app.py` (+ `wsgi.py`, `gunicorn.conf.py`, `templates/`) — Flask-интерфейс: расписания, чаты, каналы ntfy, REST API (`API.md`)
- `rund.py` — демон: проверяет расписания, шлёт в Telegram/ntfy, делает бэкапы БД (опц. scp-репликация, prod)
- `lib/cron_utils.py` — класс `VCron` (croniter + модификаторы)
- `lib/db_utils.py` — SQLite (`db/settings.db`): schedules, chats, ntfy-каналы, миграции, backup
- `lib/utils.py` — логирование, `load_env`, `get_environment_name`
- Зависимости: `requirements/{base,web,rund}.txt` (python-dotenv, pytz, python-dateutil, croniter, requests)
- Окружения: dev/prod через env (см. Readme.md, раздел «Переменные окружения»)

## Постоянные ограничения
- Python 3.11, SQLite; локально Windows, прод Linux/Docker
- Не считать старую переписку достоверным состоянием кода — сверять с репозиторием
- В git не коммитить: `db/*.db*`, `log/`, `__pycache__/`, `env`-секреты (токены Telegram) — проверить .gitignore
- Android-приложение (если появится): повышать AppVersion при каждом изменении кода; APK локально не собирать
- После каждого изменения кода: обновить `task.md`, объяснить изменения, предложить сообщения коммита
- Если GitHub или коннектор недоступны после 3 попыток (пауза ~10 с) — остановиться и сообщить, обходных путей не искать

## Рабочий процесс ИИ
1. Прочитать task.md, AI_CONTEXT.md, хвост SESSION_LOG.md
2. Сверить с репозиторием (`git log`) 
3. Экономить токены: читать файлы частично, не перечитывать неизменённое, искать grep-ом
