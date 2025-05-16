import os
import json
import tempfile
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file

from lib.cron_utils import VCron
from lib.db_utils import (DB_PATH, LOGLEVEL, LOGPATH, add_schedule,
                         delete_schedule, get_schedule, get_schedules, init_db,
                         init_log, update_schedule, add_chat, get_chats, delete_chat)
from lib.utils import MyError, get_environment_name, load_env as load_utils_env



class WebApp:
    def __init__(self, env_file=None):
        self.app = Flask(__name__, template_folder='../templates', static_folder='../static')
        self.setup_app()
        self.log = init_log('web_app', LOGPATH, LOGLEVEL)
        self.load_env(env_file)
        self.myVCron = VCron(timezone=self.timezone)
        self.setup_routes()
        init_db(drop_table=False)
        
    def setup_app(self):
        self.app.config["def_chat_id"] = os.getenv("CHAT_ID")
        self.app.config["SECRET_KEY"] = os.getenv("TLCR_SECRET_KEY", os.urandom(12).hex())
        
    def load_env(self, env_file):
        env = get_environment_name()
        load_utils_env(env)
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)

        self.db_path = DB_PATH
        self.timezone = os.getenv("TLCR_TZ", "UTC")

    def _validate_schedule_data(self, data):
        if not data or "cron" not in data or "message" not in data:
            abort(400, description="Неверный формат данных")

        if not self.myVCron.valid(data["cron"]):
            abort(400, description=f'Invalid CRON expression: "{data["cron"]}"')
        if not self.myVCron.is_valid_modifier(data.get("modifier", "")):
            abort(400, description=f'Invalid modifier expression "{data.get("modifier", "")}"')

    def setup_routes(self):
        @self.app.route('/test')
        def test_route():
            return 'ok'

        @self.app.route("/", methods=["GET", "POST"])
        def schedules_view():
            """
            Главная страница приложения. Отображает список расписаний и форму для добавления нового расписания.
            """
            if request.method == "POST":
                cron = request.form.get("cron")
                message = request.form.get("message")
                modifier = request.form.get("modifier", "")
                if not cron or not message:
                    abort(400, description="Все поля должны быть заполнены")
                try:
                    self._validate_schedule_data({"cron": cron, "modifier": modifier, "message": message}) # Validate data
                    chat_id = request.form.get("chat_id") or self.app.config["def_chat_id"]

                    if not chat_id:
                        abort(400,"Не выбран чат для напоминания. Сначала добавьте чат и выберите его.")
                    add_schedule(cron, message, modifier, int(chat_id), self.db_path)
                except ValueError as e:
                    return render_template("error.html", text=str(e)), 400
                return redirect(url_for("schedules_view"))

            sort_by = request.args.get('sort_by', 'next')
            schedules = get_schedules(self.db_path)
            chats = get_chats(self.db_path)
            chat_map = {chat['id']: chat['name'] for chat in chats} # Create a chat ID to name mapping

            for item in schedules:
                next_match = self.myVCron.get_next_match(item['cron'], item['modifier'])
                item['next'] = next_match.isoformat() if next_match else None
                item['chat_name'] = chat_map.get(item['chat_id']) # Add chat name to schedule data

            schedules.sort(
                key=lambda x: (x[sort_by] is None, x[sort_by]),
                reverse=(sort_by == 'id')
            )

            self.log.debug("Рендеринг шаблона index.html")
            chats = get_chats(self.db_path)
            return render_template("index.html", schedules=schedules, db_path=self.db_path, sort_by=sort_by, chats=chats)


        @self.app.route("/schedules", methods=["GET"])
        def list_schedules():
            """
            Возвращает список расписаний в формате JSON.
            """
            return jsonify(get_schedules(self.db_path))

        @self.app.route("/schedules_all", methods=["POST"])
        def create_schedules_by_list():
            """
            Создает несколько расписаний из списка JSON объектов.
            """
            list_data = request.get_json()
            if isinstance(list_data, list):
                if len(list_data) == 0:
                    abort(400, description="Получен пустой массив")
            else:
                abort(400, description="Ожидался массив расписаний")

            for data in list_data:
                try:
                    self._validate_schedule_data(data) # Validate data
                    add_schedule(data["cron"], data["message"], data.get("modifier", ""), self.db_path)
                except ValueError as e:
                    abort(400, description=str(e))

            return jsonify({"status": "success"}), 201

        @self.app.route("/schedules", methods=["POST"])
        def create_schedule():
            """
            Создает новое расписание.
            """
            data = request.get_json()
            try:
                self._validate_schedule_data(data) # Validate data
                add_schedule(data["cron"], data["message"], data.get("modifier", ""), self.db_path)
                return jsonify({"status": "success"}), 201
            except ValueError as e:
                abort(400, description=str(e))


        @self.app.route("/schedules/<int:schedule_id>", methods=["DELETE"])
        def remove_schedule(schedule_id: int):
            delete_schedule(schedule_id, self.db_path)
            return jsonify({"status": "deleted"})

        @self.app.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
        def delete_schedule_post(schedule_id: int):
            """
            Удаляет расписание по ID (POST запрос).
            """
            delete_schedule(schedule_id, self.db_path)
            return redirect(url_for('schedules_view'))


        @self.app.route("/schedules/<int:schedule_id>", methods=["POST"])
        def edit_schedule(schedule_id: int):
            """
            Изменяет расписание с ID=schedule_id.
            """
            data = request.get_json()
            if not data or "cron" not in data or "message" not in data:
                abort(400, description="Неверный формат данных")

            try:
                self._validate_schedule_data(data) # Validate data
                update_schedule(schedule_id, data["cron"], data["message"], data.get("modifier", ""), self.db_path)
                return jsonify({"status": "success"}), 200
            except ValueError as e:
                abort(400, description=str(e))


        @self.app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
        def edit_schedule_route(schedule_id: int):
            """
            Страница редактирования расписания.
            """
            schedule = get_schedule(schedule_id, self.db_path)
            if schedule is None:
                abort(404)

            chats = get_chats(self.db_path)

            if request.method == "GET":
                return render_template("edit.html", schedule=schedule, chats=chats)

            cron = request.form.get("cron")
            message = request.form.get("message")
            modifier = request.form.get("modifier", "")
            chat_id = request.form.get("chat_id")
            if not cron or not message or not chat_id:
                abort(400, description="Все поля должны быть заполнены")

            try:
                self._validate_schedule_data({"cron": cron, "modifier": modifier, "message": message}) # Validate data
                update_schedule(schedule_id, cron, message, modifier, self.db_path)
            except ValueError as e:
                return render_template("error.html", text=str(e)), 400
            return redirect(url_for("schedules_view"))


        @self.app.route('/list/<int:schedule_id>', methods=['GET'])
        def list_nexts(schedule_id: int):
            """
            Отображает список следующих запусков расписания.
            """
            NEXT = int(os.getenv("TLCR_LIST_ITEMS", "10"))
            schedule = get_schedule(schedule_id, self.db_path)
            if schedule is None:
                abort(404)

            next_dates = []
            cron_expression = schedule['cron']
            modifier = schedule.get('modifier')
            current_time = datetime.now(tz=self.myVCron.timezone)

            for _ in range(NEXT):
                next_match = self.myVCron.get_next_match(cron_expression, modifier, start_time=current_time)
                if next_match is None:
                    break

                next_dates.append(next_match.isoformat())
                current_time = next_match + timedelta(hours=1)

            return render_template("list.html", next_dates=next_dates, schedule=schedule)

        @self.app.route("/chats", methods=["GET", "POST"])
        def chats_view():
            if request.method == "POST":
                name = request.form.get("name")
                chat_id_str = request.form.get("chat_id")
                if not name or not chat_id_str:
                    abort(400, description="Все поля должны быть заполнены")
                try:
                    chat_id = int(chat_id_str)
                    add_chat(name, chat_id, self.db_path)
                except ValueError as e:
                    return render_template("error.html", text=str(e)), 400
                return redirect(url_for("chats_view"))

            chats = get_chats(self.db_path)
            return render_template("chats.html", chats=chats)

        @self.app.route('/chats/delete/<int:chat_id>', methods=['GET'])
        def delete_this_chat(chat_id :int):
            """
            Удаляет чат по ID.
            """
            try:
                delete_chat(chat_id, self.db_path)
            except Exception as e:
                self.log.error(f"Ошибка при удалении чата: {e}")
                return render_template("error.html", text=f"Ошибка при удалении чата: {e}"), 500
            return redirect(url_for("chats_view"))
        
        @self.app.route('/export', methods=['GET'])
        def export_json():
            """
            Экспортирует расписания в JSON файл.
            """
            schedules = get_schedules(self.db_path)
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

        @self.app.route("/drop_db", methods=["GET"])
        def reset_db():
            """
            Пересоздает базу данных.
            """
            try:
                init_db(self.db_path)
                return redirect(url_for("schedules_view"))
            except Exception as e:
                self.log.error("Ошибка при переинициализации БД: %s", str(e))
                abort(500, description="Ошибка при переинициализации БД")

        @self.app.template_filter('fromisoformat')
        def fromisoformat_filter(s: str) -> datetime or None:
            """
            Фильтр Jinja2 для преобразования строки ISO 8601 в объект datetime.
            """
            try:
                return datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        @self.app.template_filter('format_datetime')
        def format_datetime_filter(dt: datetime) -> str:
            """
            Фильтр Jinja2 для форматирования строки даты и времени.
            """
            return dt.strftime('%Y-%m-%d %H:%M %a') if dt else "##"


    def run(self):
        self.app.run(debug=os.getenv('DEBUG', 'False').lower() == 'true', port=int(os.getenv('PORT', 7878)), use_reloader=True)

web = WebApp()

if __name__ == '__main__':
    web.run()
