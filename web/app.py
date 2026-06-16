import os
import json
import tempfile
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file
from lib.cron_utils import VCron
from lib.db_utils import (
    DB_PATH, LOGLEVEL, LOGPATH,
    add_schedule, delete_schedule, get_schedule, get_schedules,
    init_db, init_log, update_schedule,
    add_chat, get_chats, delete_chat,
    add_ntfy_channel, get_ntfy_channels, delete_ntfy_channel, migrate_add_ntfy
)
from lib.utils import get_environment_name, load_env as load_utils_env


class WebApp:
    def __init__(self, env_file=None):
        self.app = Flask(__name__, template_folder='../templates', static_folder='../static')
        self.setup_app()
        self.log = init_log('web_app', LOGPATH, LOGLEVEL)
        self.load_env(env_file)
        self.myVCron = VCron(timezone=self.timezone)
        self.setup_routes()
        init_db(drop_table=False)
        migrate_add_ntfy(self.db_path)

    def setup_app(self):
        self.app.config["def_chat_id"] = os.getenv("TLCR_TELEGRAM_CHAT_ID")
        self.app.config["SECRET_KEY"] = os.getenv("TLCR_SECRET_KEY", os.urandom(12).hex())

    def load_env(self, env_file):
        env = get_environment_name()
        load_utils_env(env)
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)

        self.db_path = DB_PATH
        self.timezone = os.getenv("TLCR_TZ", "UTC")

    @staticmethod
    def _calculate_age_for_date(birth_date: datetime, at_date: datetime) -> int:
        years = at_date.year - birth_date.year
        if (at_date.month, at_date.day) < (birth_date.month, birth_date.day):
            years -= 1
        return years

    def _validate_schedule_data(self, data):
        if not data or "cron" not in data or "message" not in data:
            abort(400, description="Неверный формат данных")

        if not self.myVCron.valid(data["cron"]):
            abort(400, description=f'Invalid CRON expression: "{data["cron"]}"')

        # Валидация модификатора через VCron.check_modifier
        modifier = data.get("modifier", "") or ""
        if modifier:
            try:
                now = datetime.now(tz=self.myVCron.timezone)
                # check_modifier возвращает bool: False трактуем как неверный модификатор
                if not self.myVCron.check_modifier(modifier, now):
                    abort(400, description=f'Invalid modifier expression "{modifier}"')
            except Exception:
                abort(400, description=f'Invalid modifier expression "{modifier}"')

    def setup_routes(self):
        @self.app.route('/test')
        def test_route():
            return 'ok'

        @self.app.route("/", methods=["GET", "POST"])
        def schedules_view():
            if request.method == "POST":
                cron = request.form.get("cron")
                message = request.form.get("message")
                modifier = request.form.get("modifier", "")
                if not cron or not message:
                    abort(400, description="Все поля должны быть заполнены")
                try:
                    self._validate_schedule_data({"cron": cron, "modifier": modifier, "message": message})
                    chat_id = request.form.get("chat_id") or self.app.config["def_chat_id"]
                    if not chat_id:
                        abort(400, "Не выбран чат для напоминания. Сначала добавьте чат и выберите его.")
                    ntfy_id_str = request.form.get("ntfy_id", "")
                    ntfy_id = int(ntfy_id_str) if ntfy_id_str else None
                    add_schedule(cron, message, modifier, int(chat_id), self.db_path, ntfy_id=ntfy_id)
                except ValueError as e:
                    return render_template("error.html", text=str(e)), 400
                return redirect(url_for("schedules_view"))

            sort_by = request.args.get('sort_by', 'next')
            schedules = get_schedules(self.db_path)
            chats = get_chats(self.db_path)
            chat_map = {chat['id']: chat['name'] for chat in chats}

            for item in schedules:
                next_match = self.myVCron.get_next_match(item['cron'], item['modifier'])
                item['next'] = next_match.isoformat() if next_match else None
                item['chat_name'] = chat_map.get(item['chat_id'])

            schedules.sort(
                key=lambda x: (x[sort_by] is None, x[sort_by]),
                reverse=(sort_by == 'id')
            )

            self.log.debug("Рендеринг шаблона index.html")
            chats = get_chats(self.db_path)
            ntfy_channels = get_ntfy_channels(self.db_path)
            tag = os.getenv("TAG", "dev")
            return render_template(
                "index.html",
                schedules=schedules, db_path=self.db_path,
                sort_by=sort_by, chats=chats, tag=tag,
                ntfy_channels=ntfy_channels
            )

        @self.app.route("/message/<int:schedule_id>", methods=["GET"])
        def show_message_file(schedule_id: int):
            schedule = get_schedule(schedule_id, self.db_path)
            if not schedule:
                abort(404, description="Расписание не найдено")
            message = schedule.get("message", "")
            if not message.startswith("#!"):
                abort(400, description="Сообщение не содержит путь к файлу")
            file_path = message[2:].strip()
            if not os.path.isfile(file_path):
                abort(404, description=f"Файл не найден: {file_path}")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                if not isinstance(rows, list) or not all(
                    isinstance(row, dict) and "date" in row and "text" in row for row in rows
                ):
                    abort(400, description="Файл должен содержать список словарей с ключами 'date' и 'text'")
            except Exception as e:
                abort(400, description=f"Ошибка чтения JSON файла: {e}")

            tag = os.getenv("TAG", "dev")
            return render_template("message_file.html", rows=rows, schedule=schedule, tag=tag)

        @self.app.route("/schedules", methods=["GET"])
        def list_schedules():
            return jsonify(get_schedules(self.db_path))

        @self.app.route("/schedules_all", methods=["POST"])
        def create_schedules_by_list():
            list_data = request.get_json()
            if isinstance(list_data, list):
                if len(list_data) == 0:
                    abort(400, description="Получен пустой массив")
            else:
                abort(400, description="Ожидался массив расписаний")

            for data in list_data:
                try:
                    self._validate_schedule_data(data)
                    add_schedule(data["cron"], data["message"], data.get("modifier", ""), self.db_path)
                except ValueError as e:
                    abort(400, description=str(e))

            return jsonify({"status": "success"}), 201

        @self.app.route("/schedules", methods=["POST"])
        def create_schedule():
            data = request.get_json()
            try:
                self._validate_schedule_data(data)
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
            delete_schedule(schedule_id, self.db_path)
            return redirect(url_for('schedules_view'))

        @self.app.route("/schedules/<int:schedule_id>", methods=["POST"])
        def edit_schedule(schedule_id: int):
            data = request.get_json()
            if not data or "cron" not in data or "message" not in data or "chat_id" not in data:
                abort(400, description="Неверный формат данных")

            try:
                self._validate_schedule_data(data)
                update_schedule(
                    schedule_id,
                    data["cron"],
                    data["message"],
                    data.get("modifier", ""),
                    int(data["chat_id"]),
                    self.db_path
                )
                return jsonify({"status": "success"}), 200
            except ValueError as e:
                abort(400, description=str(e))

        @self.app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
        def edit_schedule_route(schedule_id: int):
            schedule = get_schedule(schedule_id, self.db_path)
            if schedule is None:
                abort(404)

            chats = get_chats(self.db_path)
            ntfy_channels = get_ntfy_channels(self.db_path)

            if request.method == "GET":
                return render_template(
                    "edit.html",
                    schedule=schedule, chats=chats, ntfy_channels=ntfy_channels
                )

            cron = request.form.get("cron")
            message = request.form.get("message")
            modifier = request.form.get("modifier", "")
            chat_id = request.form.get("chat_id")
            ntfy_id_str = request.form.get("ntfy_id", "")
            ntfy_id = int(ntfy_id_str) if ntfy_id_str else None

            if not cron or not message or not chat_id:
                abort(400, description="Все поля должны быть заполнены")

            try:
                self._validate_schedule_data({"cron": cron, "modifier": modifier, "message": message})
                update_schedule(
                    schedule_id, cron, message, modifier,
                    int(chat_id), self.db_path, ntfy_id=ntfy_id
                )
            except ValueError as e:
                return render_template("error.html", text=str(e)), 400
            return redirect(url_for("schedules_view"))

        @self.app.route('/list/<int:schedule_id>', methods=['GET'])
        def list_nexts(schedule_id: int):
            NEXT = int(os.getenv("TLCR_LIST_ITEMS", "10"))
            schedule = get_schedule(schedule_id, self.db_path)
            if schedule is None:
                abort(404)

            cron_expression = schedule['cron']
            modifier = schedule.get('modifier')
            message = schedule.get('message', '') or ''
            current_time = datetime.now(tz=self.myVCron.timezone)

            rows = []
            birth_date = None
            is_birthday = isinstance(message, str) and message.startswith("ДР") and modifier

            if is_birthday:
                try:
                    birth_date = datetime.strptime(modifier.strip(), "%Y%m%d")
                except ValueError:
                    birth_date = None
                    is_birthday = False

            for _ in range(NEXT):
                next_match = self.myVCron.get_next_match(
                    cron_expression, modifier, start_time=current_time
                )
                if next_match is None:
                    break

                if is_birthday and birth_date is not None:
                    age = self._calculate_age_for_date(birth_date, next_match)
                    text = f"{message} ({age} лет)"
                else:
                    text = message

                rows.append({"dt": next_match, "text": text})
                current_time = next_match + timedelta(hours=1)

            return render_template("list.html", rows=rows, schedule=schedule)

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
        def delete_this_chat(chat_id: int):
            try:
                delete_chat(chat_id, self.db_path)
            except Exception as e:
                self.log.error(f"Ошибка при удалении чата: {e}")
                return render_template("error.html", text=f"Ошибка при удалении чата: {e}"), 500
            return redirect(url_for("chats_view"))

        @self.app.route("/ntfy", methods=["GET", "POST"])
        def ntfy_view():
            if request.method == "POST":
                name = request.form.get("name")
                url = request.form.get("url")
                title = request.form.get("title", "")
                if not name or not url:
                    abort(400, description="Название и URL обязательны")
                try:
                    add_ntfy_channel(name, url, title or None, self.db_path)
                except Exception as e:
                    return render_template("error.html", text=str(e)), 400
                return redirect(url_for("ntfy_view"))

            channels = get_ntfy_channels(self.db_path)
            return render_template("ntfy.html", channels=channels)

        @self.app.route("/ntfy/delete/<int:channel_id>", methods=["GET"])
        def delete_ntfy_channel_view(channel_id: int):
            try:
                delete_ntfy_channel(channel_id, self.db_path)
            except Exception as e:
                self.log.error(f"Ошибка при удалении ntfy канала: {e}")
                return render_template("error.html", text=f"Ошибка при удалении ntfy канала: {e}"), 500
            return redirect(url_for("ntfy_view"))

        @self.app.route('/export', methods=['GET'])
        def export_json():
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

        @self.app.route("/api_doc", methods=["GET"])
        def download_api_doc():
            """Отдать API-док как файл, сгенерированный из API_DOC_TEXT."""
            # пишем во временный файл, чтобы send_file отдал attachment
            tmp = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".md", encoding="utf-8")
            try:
                tmp.write(API_DOC_TEXT)
                tmp.flush()
                tmp.close()
                return send_file(
                    tmp.name,
                    mimetype="text/markdown",
                    as_attachment=True,
                    download_name="API.md",
                )
            finally:
                # файл удалится автоматически системой после рестарта/очистки temp;
                # можно не удалять вручную, чтобы не гоняться за временем жизни ответа
                pass

        @self.app.route("/drop_db", methods=["GET"])
        def reset_db():
            try:
                init_db(self.db_path)
                migrate_add_ntfy(self.db_path)
                return redirect(url_for("schedules_view"))
            except Exception as e:
                self.log.error("Ошибка при переинициализации БД: %s", str(e))
                abort(500, description="Ошибка при переинициализации БД")

        @self.app.template_filter('fromisoformat')
        def fromisoformat_filter(s: str) -> datetime or None:
            try:
                return datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        @self.app.template_filter('format_datetime')
        def format_datetime_filter(dt: datetime) -> str:
            return dt.strftime('%Y-%m-%d %H:%M %a') if dt else "##"

    def run(self):
        self.app.run(
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            port=int(os.getenv('TLCR_FLASK_PORT', 7999)),
            use_reloader=True
        )


web = WebApp()

if __name__ == '__main__':
    web.run()
