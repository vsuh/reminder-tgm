# API

Приложение предоставляет REST API для управления расписаниями.

## Получение списка расписаний

```text
GET /schedules
```

Ответ:

```json
[
  {
    "id": 1,
    "cron": "0 12 * * *",
    "message": "test message 1",
    "modifier": "",
    "last_fired": "2025-03-23T12:00:00"
  },
  {
    "id": 2,
    "cron": "0 13 * * *",
    "message": "test message 2",
    "modifier": "d/2",
    "last_fired": null
  },
  ...
]
```

## Создание расписания

```text
POST /schedules
```

- Заголовки:

```http
Content-Type: application/json;
charset: utf-8
```

Тело запроса (JSON):

```json
{
  "cron": "0 15 * * *",
  "message": "new schedule message",
  "modifier": "w/2"
}
```

Ответ:

```json
{
  "status": "success"
}
```

## Создание нескольких расписаний

```text
POST /schedules_all
```

Заголовки:

```http
Content-Type: application/json;
charset: utf-8
```

Тело запроса (JSON):

```json
[
    {
        "cron": "1 13 * * *",
        "message": "event 1",
        "modifier": "20250303>d/60"
    },
    {
        "cron": "2 13 * * *",
        "message": "event 2",
        "modifier": "20250303>w/2"
    }
]
```

Ответ:

```json
{
  "status": "success"
}
```

## Удаление расписания

```text
DELETE /schedules/<id>
```

Ответ:

```json
{
  "status": "deleted"
}
```

## Редактирование расписания

```text
POST /schedules/<id>
```

Заголовки:

```http
Content-Type: application/json;
charset: utf-8
```

Тело запроса (JSON):

```json
{
  "cron": "0 16 * * *",
  "message": "updated schedule message",
  "modifier": "d/3"
}
```

Ответ: В случае успеха возвращается код 302 (редирект на главную страницу). В случае ошибки возвращается код 500 и страница с описанием ошибки.

