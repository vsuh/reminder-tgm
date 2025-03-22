# Робот-напоминатель в TELEGRAM

Скрипт на Python.
Запускается каждый час и проверяет, соответствует ли время его запуска cron-выражению из настроек.
Если соответствует, то берет сообщение из соответствующего блока настроек и отправляет его в чат телеграм.
Расписания хранятся в sqlite базе.


> Допустим, требуется, начиная с 01.04 отправлять уведомление каждые 17 дней. Т.е. 17.04, 04.05, 21.05, 07.06 и т.д.
> cron выражение типа "`1 12 */17 * *`" будет срабатывать 17.04, 17.05, 17.06, что задачу не решает. Поэтому, еще используется необязательный уточнятель cron-выражения `modifier`. Он проверяется после срабатывания cron-выражения и служит для уточнения времени срабатывания расписания.
> `d/n` срабатывает раз в `n` дней, а `w/n`, соответственно, каждые `n` недель.
> Для решения посавленной задачи, нужно установить cron-выражение на срабатывание каждый день: "`0 12 * * *`", а модификатором ограничить срабатывание каждый 17 день: `d/17`, если неважно с какой даты начинать отсчет (тогда отсчет начинается с начала века), и `20220224>d/17`, если важно.

TODO: расширить модификатор до YYYYMMDD>[d|w]/N*n - выполнить только n раз

Для отправки сообщений в телеграм чат требуются токен телеграм бота и id чата. Они хранятся в файлах `.env`
В `windows` загружается файл `.env.dev`, в `linux` - `.env.prod`: [файл .env](.env.SAMPLE)

Для обслуживания расписания при отладке, скриптом `palmface.sh` запускается веб-интерфейс `http://localhost:7878` таблицы расписания (sqlite).

## Запуск в проде

Создать файл службы `cron-telegram-reminder` для `systemd`

```sh
sudo nano /etc/systemd/system/cron-telegram-reminder.service
```
вставить туда, заменив USER и WORKDIR на правильные значения

```ini
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

