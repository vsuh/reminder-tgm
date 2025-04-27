import logging
import os
import sys
import json
import tempfile
from datetime import datetime, timedelta

from lib.utils import init_log, get_environment_name, load_env, MyError
from lib.cron_utils import VCron
# from app import app
from lib.db_utils import init_db, get_schedules, get_schedule, update_schedule, delete_schedule, add_schedule
from flask import (Flask,jsonify, render_template, redirect, url_for, abort,
                   send_file, request, g)

APIPORT=7870
# def create_app(environ=None, start_response=None, environment_name: str = None):
def create_app(environment_name: str = None):
    # Load environment variables
    if environment_name is None:
        environment = get_environment_name()
    else:
        environment = environment_name
    load_env(environment)

    # Read environment variables
    TIMEZONE = os.getenv("reminderTZ", "UTC")
    DB_PATH = os.getenv("DB_PATH", "settings.db")
    LOGPATH = os.getenv("LOGPATH", ".")
    LOGLEVEL = os.getenv("LOG_LEVEL", 'INFO').upper()
    APIPORT = os.getenv("PORT", "7878")
    SECRET_KEY = os.getenv("SECRET_KEY")
    ISDEBUGMODE = os.getenv("DEBUG", False).lower() in ('true', 'yes', '1')

    app = Flask(__name__) # Create Flask app instance

    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DEBUG'] = ISDEBUGMODE
    app.config['TIMEZONE'] = TIMEZONE
    app.config['DB_PATH'] = DB_PATH
    app.config['SERVER_NAME'] = f"localhost:{APIPORT}" if environment == 'dev' else f"0.0.0.0:{APIPORT}"
    app.config['myVCron'] = VCron(TIMEZONE)
    app.config['APIPORT'] = APIPORT
    app.template_folder = 'templates'

    # Initialize database
    init_db(DB_PATH, False)

    # Initialize logger
    log = init_log('svrm', LOGPATH, LOGLEVEL)
    app.config['log'] = log # Add logger to app.config

    @app.route("/", methods=["GET", "POST"])
    def schedules_view():
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
                return render_template("error.html", text=str(e)), 400  # Обработка неверного ввода
            return redirect(url_for("schedules_view"))

        sort_by = request.args.get('sort_by', 'next')  # Get sort column from query parameter
        schedules = get_schedules(app.config['DB_PATH'])
        for item in schedules:
            next_match = app.config['myVCron'].get_next_match(item['cron'], item['modifier'])
            item['next'] = next_match.isoformat() if next_match else None
        # Sort schedules based on the selected column
        schedules.sort(
            key=lambda x: (x[sort_by] is None, x[sort_by])
            , reverse=(sort_by == 'id')
        )

        db_path = app.config['DB_PATH']
        app.logger.debug("Рендеринг шаблона index.html")
        return render_template("index.html", schedules=schedules, db_path=db_path, sort_by=sort_by)



    @app.route("/schedules", methods=["GET"])
    def list_schedules():
        """
        Возвращает список расписаний в формате JSON.

        Returns:
            str: JSON представление списка расписаний.
        """
        return jsonify(get_schedules(app.config['DB_PATH'])) # Pass DB_PATH

    @app.route("/schedules_all", methods=["POST"])
    def create_schedules_by_list():
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
            if not app.config['myVCron'].valid(data["cron"]):
                raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
            if not app.config['myVCron'].is_valid_modifier(data.get("modifier", "")):
                raise ValueError(f'Invalid modifier expression "{data.get("modifier", "")}"')

            add_schedule(data["cron"], data["message"], data.get("modifier", ""))

        return jsonify({"status": "success"}), 201

    @app.route("/schedules", methods=["POST"])
    def create_schedule():
        """
        Создает новое расписание.

        Returns:
            tuple: Кортеж, содержащий JSON ответ и код состояния.

        Raises:
            ValueError: Если cron или modifier некорректны.
        """
        data = request.get_json()
        if not data or "cron" not in data or "message" not in data:
            abort(400, description="Неверный формат данных")

        if not app.config['myVCron'].valid(data["cron"]):
            raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
        if not app.config['myVCron'].is_valid_modifier(data.get("modifier", "")):
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
        return redirect(url_for('schedules_view'))


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
        modifier = data.get("modifier", "")

        if not app.config['myVCron'].valid(cron):
            raise ValueError(f'Invalid CRON expression: "{cron}"')

        if not app.config['myVCron'].is_valid_modifier(modifier):
            raise ValueError(f'Invalid modifier expression "{modifier}"')

        try:
            update_schedule(schedule_id, cron, message, modifier)
        except ValueError as e:
            return render_template("error.html", text=str(e)), 400
        return redirect(url_for("schedules_view"))


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

        if request.method == "GET":
            return render_template("edit.html", schedule=schedule)

        cron = request.form.get("cron")
        message = request.form.get("message")
        modifier = request.form.get("modifier", "")
        if not cron or not message:
            abort(400, description="Все поля должны быть заполнены")

        try:
            update_schedule(schedule_id, cron, message, modifier)
        except ValueError as e:
            return render_template("error.html", text=str(e)), 400
        return redirect(url_for("schedules_view"))


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
        current_time = datetime.now(tz=app.config['myVCron'].timezone)

        for _ in range(NEXT):
            next_match = app.config['myVCron'].get_next_match(cron_expression, modifier, start_time=current_time)
            if next_match is None:
                break
            next_dates.append(next_match.isoformat())
            current_time = next_match + timedelta(seconds=1)

        return render_template("list.html", next_dates=next_dates, schedule=schedule)

    @app.route('/export', methods=['GET'])
    def export_json():
        """
        Экспортирует расписания в JSON файл.

        Returns:
            flask.wrappers.Response: JSON файл с расписаниями.
        """
        schedules = get_schedules(app.config['DB_PATH']) # Pass DB_PATH
        json_data = json.dumps(schedules, indent=4, ensure_ascii=False)
        with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.json', encoding='utf-8') as temp_file:
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
            init_db(app.config['DB_PATH'])
            return redirect(url_for("schedules_view"))

        except Exception as e:
            app.logger.error("Ошибка при переинициализации БД: %s", str(e))
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

    return app

def application(environ, start_response):
    return app(environ, start_response)


if __name__ == "__main__":
    from waitress import serve
    environment = get_environment_name()
    load_env(environment)

    SERVE_PORT = os.getenv("PORT", 7878)
    if environment == 'dev':
        app = create_app()
        app.run(debug=True, host='0.0.0.0', port=int(SERVE_PORT))
    else:
        serve(application, host='0.0.0.0', port=int(SERVE_PORT))
