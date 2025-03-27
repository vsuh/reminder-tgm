import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta

import pytz
from croniter import croniter
from dateutil.relativedelta import relativedelta
from flask import (Flask, abort, g, jsonify, redirect, render_template,
        request, send_file, url_for)

from lib.utils import init_log
from lib.cron_utils import VCron
from lib.db_utils import (add_schedule, delete_schedule, get_schedule,
        get_schedules, init_db, update_schedule)
from lib.utils import MyError, get_environment_name, init_log, load_env

# Load environment variables
environment = get_environment_name()
load_env(environment)

app = Flask(__name__)

# Функции работы с БД
def get_schedules()-> list:
    """
    Возвращает список расписаний из базы данных.

    Returns:
        list: Список расписаний в виде словарей.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules")
            return [{"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписаний: %s", str(e))
        return []

def get_schedule(schedule_id: int):
    '''
    Возвращает расписание по его ID.

    Args:
        schedule_id (int): ID расписания.

    Returns:
        dict or None: Расписание в виде словаря или None, если расписание не найдено.
    '''
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4]}
            else:
                return None
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписания: %s", str(e))
        return []

def add_schedule(cron: str, message: str, modifier: str):
    """
    Добавляет новое расписание в базу данных.

    Args:
        cron (str): CRON выражение.
        message (str): Сообщение.
        modifier (str, optional): Модификатор. По умолчанию "".

    Raises:
        ValueError: Если cron или modifier некорректны.
    """
    if not myVCron.valid(cron):
        raise ValueError(f'Invalid CRON expression: "{cron}"')
    if not myVCron.is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO schedules (cron, message, modifier) VALUES (?, ?, ?)", (cron, message, modifier))
            conn.commit()
            log.info("Добавлено новое расписание: %s, %s, %s", cron, message, modifier)
    except sqlite3.Error as e:
        log.error("Ошибка при добавлении расписания: %s", str(e))

def delete_schedule(schedule_id: int):
    """
    Удаляет расписание из базы данных.

    Args:
        schedule_id (int): ID расписания.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            log.info("Удалено расписание с ID: %d", schedule_id)
    except sqlite3.Error as e:
        log.error("Ошибка при удалении расписания: %s", str(e))

def update_schedule(schedule_id: int, cron: str, message: str, modifier: str) -> MyError or None:
    """
    Обновляет расписание в базе данных.

    Args:
        schedule_id (int): ID расписания.
        cron (str): CRON выражение.
        message (str): Сообщение.
        modifier (str, optional): Модификатор. По умолчанию "".

    Returns:
        MyError or None: Возвращает MyError, если произошла ошибка, или None в случае успеха.

    Raises:
        ValueError: Если cron или modifier некорректны.
    """
    if not myVCron.valid(cron):
        log.error(f'Invalid CRON expression: "{cron}"')
        return MyError(f'Invalid CRON expression: "{cron}"') 
    if not myVCron.is_valid_modifier(modifier):
        log.error(f'Invalid modifier expression "{modifier}"')
        return MyError(f'Invalid modifier expression "{modifier}"') 

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET cron = ?, message = ?, modifier = ? WHERE id = ?", (cron, message, modifier, schedule_id))
            conn.commit()
            log.info("Обновлено расписание с ID: %d", schedule_id)
        return None
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении расписания: %s", str(e))

# Эндпоинты Flask API

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Главная страница приложения. Отображает список расписаний и форму для добавления нового расписания.

    Returns:
        str: HTML код страницы.
    """
    if request.method == "POST":
        cron = request.form.get("cron")
        message = request.form.get("message")
        modifier = request.form.get("modifier", "")
        if not cron or not message:
            abort(400, description="Все поля должны быть заполнены")
        try:
            add_schedule(cron, message, modifier)
        except ValueError as e:
            return render_template("error.html", text=str(e)), 400 # Обработка неверного ввода
        return redirect(url_for("index"))

    sort_by = request.args.get('sort_by', 'next') # Get sort column from query parameter
    schedules = []
    for item in get_schedules():
        next_match = myVCron.get_next_match(item['cron'], item['modifier'])
        schedules.append({**item, 'next': next_match.isoformat() if next_match else None})

    # Sort schedules based on the selected column
    schedules.sort(
        key=lambda x: (x[sort_by] is None, x[sort_by])
        , reverse=(sort_by == 'id')
    )

    db_path = DB_PATH
    return render_template("index.html", schedules=schedules, db_path=db_path, sort_by=sort_by)

@app.route("/schedules", methods=["GET"])
def list_schedules():
    """
    Возвращает список расписаний в формате JSON.

    Returns:
        str: JSON представление списка расписаний.
    """
    return jsonify(get_schedules())

@app.route("/schedules_all", methods=["POST"])
def create_schedules_by_list():
    """
    Создает новое расписание.

    Returns:
        tuple: Кортеж, содержащий JSON ответ и код состояния.

    Raises:
        ValueError: Если cron или modifier некорректны.
    """
    """
    Создает несколько расписаний из списка JSON объектов.

    Returns:
        tuple: Кортеж, содержащий JSON ответ и код состояния.
    """
    list_data = request.get_json()
    if isinstance(list_data, list):
        if len(list_data)==0:
            abort(400, description="Получен пустой массив")
    else:
        abort(400, description="Ожидался массив расписаний")
         
    for data in list_data:
        if not data or "cron" not in data or "message" not in data:
            abort(400, description="Неверный формат данных")
        if not myVCron.valid(data["cron"]):
            raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
        if not myVCron.is_valid_modifier(data.get("modifier", "")):
            raise ValueError(f'Invalid modifier expression "{data.get("modifier", "")}"')

        add_schedule(data["cron"], data["message"], data.get("modifier", ""))
    
    return jsonify({"status": "success"}), 201

@app.route("/schedules", methods=["POST"])
def create_schedule():
    """
    Удаляет расписание по ID (POST запрос).

    Args:
        schedule_id (int): ID расписания.

    Returns:
        flask.wrappers.Response: Редирект на главную страницу.
    """
    data = request.get_json()
    if not data or "cron" not in data or "message" not in data:
        abort(400, description="Неверный формат данных")

    if not myVCron.valid(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    if not myVCron.is_valid_modifier(data.get("modifier", "")):
        raise ValueError(f'Invalid modifier expression "{data.get("modifier", "")}"')

    add_schedule(data["cron"], data["message"], data.get("modifier", ""))
    return jsonify({"status": "success"}), 201

@app.route("/schedules/<int:schedule_id>", methods=["DELETE"])
def remove_schedule(schedule_id: int):
    delete_schedule(schedule_id)
    return jsonify({"status": "deleted"})

@app.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
def delete_schedule_post(schedule_id: int):
    """
    Удаляет расписание по ID (POST запрос).

    Args:
        schedule_id (int): ID расписания.

    Returns:
        flask.wrappers.Response: Редирект на главную страницу.
    """
    delete_schedule(schedule_id)
    return redirect(url_for('index'))

@app.route("/schedules/<int:schedule_id>", methods=["POST"])
def edit_schedule(schedule_id: int):
    """
    Изменяет расписание с ID=schedule_id.

    Args:
        schedule_id (int): ID расписания.

    Returns:
        flask.wrappers.Response: Редирект на главную страницу или HTML код страницы с ошибкой.

    Raises:
        ValueError: Если cron или modifier некорректны.
    """
    data = request.get_json()
    if not data or "cron" not in data or "message" not in data:
        abort(400, description="Неверный формат данных")
    cron = data["cron"]
    message = data["message"]
    modifier = data["modifier"]

    if not myVCron.valid(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    modifier = data.get("modifier", "")
    if not myVCron.is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')
    
    update_result = update_schedule(schedule_id, cron, message, modifier)
    return (redirect(url_for("index")) if update_result is None else render_template("error.html", text=str(update_result)))

@app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit_schedule_route(schedule_id: int):
    """
    Страница редактирования расписания.

    Args:
        schedule_id (int): ID расписания.

    Returns:
        str or flask.wrappers.Response: HTML код страницы редактирования или редирект на главную страницу.
    """
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)

    if request.method != "POST":
        return render_template("edit.html", schedule=schedule)
    cron = request.form.get("cron")
    message = request.form.get("message")
    modifier = request.form.get("modifier", "")
    if not cron or not message:
        abort(400, description="Все поля должны быть заполнены")
    update_result = update_schedule(schedule_id, cron, message, modifier)
    return (redirect(url_for("index")) if update_result is None else render_template("error.html", text=str(update_result)))

@app.route('/list/<int:schedule_id>', methods=['GET'])
def list_nexts(schedule_id: int):
    """
    Отображает список следующих запусков расписания.

    Args:
        schedule_id (int): ID расписания.

    Returns:
        str: HTML код страницы со списком следующих запусков.
    """
    NEXT = 10
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)

    next_dates = []
    cron_expression = schedule['cron']
    modifier = schedule.get('modifier')
    current_time = datetime.now(tz=myVCron.timezone) # Add timezone to current_time

    for _ in range(NEXT):
        next_match = myVCron.get_next_match(cron_expression, modifier, start_time=current_time)
        if next_match is None:
            break  # Прекращаем, если больше нет совпадений
        next_dates.append(next_match.isoformat())
        current_time = next_match + timedelta(seconds=1) # Add one second to avoid same match

    return render_template("list.html", next_dates=next_dates, schedule=schedule)

@app.route('/export', methods=['GET'])
def export_json():
    """
    Экспортирует расписания в JSON файл.

    Returns:
        flask.wrappers.Response: JSON файл с расписаниями.
    """
    schedules = get_schedules()
    json_data = json.dumps(schedules, indent=4, ensure_ascii=False)
    with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.json') as temp_file:
        temp_file.write(json_data)
        temp_file.flush()

    return send_file(
        temp_file.name, 
        mimetype='application/json', 
        as_attachment=True, 
        download_name='schedules_export.json'
    )

@app.route("/drop_db", methods=["GET"])
def reset_db():
    """
    Пересоздает базу данных.

    Returns:
        flask.wrappers.Response: Редирект на главную страницу.
    """
    try:
        init_db(DB_PATH)
        return redirect(url_for("index"))

    except Exception as e:
        log.error("Ошибка при переинициализации БД: %s", str(e))
        abort(500, description="Ошибка при переинициализации БД")

@app.template_filter('fromisoformat')
def fromisoformat_filter(s: str) -> datetime or None:
    """
    Фильтр Jinja2 для преобразования строки ISO 8601 в объект datetime.

    Args:
        s (str): Строка ISO 8601.

    Returns:
        datetime or None: Объект datetime или None, если строка некорректна.
    """
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):  # Handle cases where s is None or not a valid ISO string
        return None

@app.template_filter('format_datetime')
def format_datetime_filter(dt: datetime) -> str:
    """
    Фильтр Jinja2 для форматирования строки даты и времени.

    Args:
        dt (datetime): Объект datetime.

    Returns:
        str: Отформатированная строка даты и времени.
    """
    return dt.strftime('%Y-%m-%d %H:%M') if dt else "##" # Handle None values

if __name__ == "__main__":
    log.info(f"Запуск Flask-сервера: http://localhost:{APIPORT}")
    app.run(host="0.0.0.0", port=APIPORT)
