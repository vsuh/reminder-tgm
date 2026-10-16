from croniter import croniter
from datetime import datetime
import pytz
from dateutil.relativedelta import relativedelta
import os
import re
import os
from .utils import init_log, get_environment_name, load_env

environment = get_environment_name()
load_env(environment)

LOGPATH = os.getenv("TLCR_LOGPATH", ".")
LOGLEVEL = os.getenv("TLCR_LOG_LEVEL", 'INFO').upper()
log = init_log('cron_utils', LOGPATH, LOGLEVEL)

ONCE_CRON = "@once"  # маркер однократного напоминания в поле schedules.cron
ONCE_FORMAT = "%Y-%m-%d %H:%M"  # формат хранения run_at (локальное время TIMEZONE)


class VCron:
    """
    Класс для работы с cron выражениями и модификаторами.
    """

    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)

    def check_cron(self, cron_expression: str, date: datetime) -> bool:
        cron_expression = self._remove_minutes(cron_expression)
        return croniter.match(cron_expression, date)

    def _remove_minutes(self, cron: str)->str:
        cron_parts = cron.split()
        cron_parts[0] = "*" 
        return " ".join(cron_parts)

    # --- однократные напоминания ---

    def parse_once(self, text: str, now: datetime | None = None, default_time: str | None = None) -> str:
        """
        Разбирает ввод «когда» и возвращает строку 'YYYY-MM-DD HH:MM' (время TIMEZONE).
        Форматы: 'YYYY-MM-DD HH:MM', 'DD.MM.YYYY HH:MM', 'HH:MM' (сегодня),
        'YYYY-MM-DD' / 'DD.MM.YYYY' (время по умолчанию, TLCR_ONCE_DEFAULT_TIME=14:00).
        Срабатывание округляется вниз до часа, поэтому «прошлым» считается
        только час, который уже закончился. Бросает ValueError.
        """
        now = now or datetime.now(tz=self.timezone)
        default_time = default_time or os.getenv("TLCR_ONCE_DEFAULT_TIME", "14:00")
        text = (text or "").strip().replace("T", " ")
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                pass
        if dt is None:
            for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    d = datetime.strptime(text, fmt).date()
                    t = datetime.strptime(default_time, "%H:%M").time()
                    dt = datetime.combine(d, t)
                    break
                except ValueError:
                    pass
        if dt is None:
            try:
                t = datetime.strptime(text, "%H:%M").time()
                dt = datetime.combine(now.date(), t)
            except ValueError:
                raise ValueError(
                    f'Неверный формат времени "{text}". Допустимо: '
                    '"ГГГГ-ММ-ДД ЧЧ:ММ", "ЧЧ:ММ", "ГГГГ-ММ-ДД"'
                )
        dt = self.timezone.localize(dt)
        if dt.replace(minute=0) < now.replace(minute=0, second=0, microsecond=0):
            raise ValueError(f'Время "{dt.strftime(ONCE_FORMAT)}" уже в прошлом')
        return dt.strftime(ONCE_FORMAT)

    def once_datetime(self, run_at: str) -> datetime:
        """Точное время однократного напоминания (aware)."""
        return self.timezone.localize(datetime.strptime(run_at, ONCE_FORMAT))

    def is_once_due(self, run_at: str, now: datetime) -> bool:
        """Пора ли отправлять: now >= начало часа run_at (точность — час)."""
        return self.once_datetime(run_at).replace(minute=0) <= now

    def valid(self, cron_expression: str) -> bool:
        try:
            croniter(cron_expression)  # Directly check with croniter
            return True
        except ValueError:
            return False

    def valid_modifier(self, modifier: str) -> bool:
        if not modifier:
            return True

        parts = modifier.split(">")
        if len(parts) > 2:
            return False
            
        start_date_str = parts[0] if len(parts) == 2 else "20010101"
        rule = parts[-1]

        try:
            datetime.strptime(start_date_str, "%Y%m%d")
        except ValueError:
            return False

        if rule.startswith(("w/", "d/", "m/")):
            try:
                interval = int(rule[2:])
                return True
            except ValueError:
                return False
        return False

    def check_modifier(self, modifier: str, now: datetime) -> bool:
        log.debug(f"check_modifier started with modifier='{modifier}', now={now}")
        now = now.replace(tzinfo=self.timezone) # Ensure now has the correct timezone
        if not modifier:
            log.debug("Modifier is empty, returning True")
            return True

        parts = modifier.split(">")
        start_date_str = parts[0] if len(parts) == 2 else "20010101"
        rule = parts[-1]
        log.debug(f"start_date_str='{start_date_str}', rule='{rule}'")

        try:
            start_datetime = self.timezone.localize(datetime.combine(datetime.strptime(start_date_str, "%Y%m%d").date(), datetime.min.time()))
        except OverflowError:
            start_datetime = self.timezone.localize(datetime(2001, 1, 1)) # Fallback to a safe date
        except ValueError:
            log.debug("Invalid start date format, returning False")
            return False # Invalid date format

        if rule.startswith(("w/", "d/", "m/")):  # Handle all three types
            interval = int(rule[2:])
            delta = relativedelta(now, start_datetime)
            days_since = self.days_since(now.date(), start_datetime.date(), )
            log.debug(f"Interval={interval}, delta={delta}, days_since={days_since}")

            if rule.startswith("w/"):
                weeks = int(days_since/7)
                res = (weeks % interval == 0) and (days_since%7 == 0)
                log.debug(f"w/ rule check result: {res}")
                return res
            elif rule.startswith("d/"):
                res = days_since % interval == 0
                log.debug(f"d/ rule check result: {res}")
                return res
            elif rule.startswith("m/"):
                months = delta.years * 12 + delta.months
                res = (months % interval == 0) and (now.day == start_datetime.day)
                log.debug(f"m/ rule check result: {res}")
                return res
            return True
        else:
            log.debug("Unknown rule format, returning False")
            return False

    def days_since(self, today_date:datetime.date, base_date: datetime.date) -> int:
        delta = today_date - base_date
        return delta.days

    def get_next_match(self, cron_expression: str, modifier: str = None, start_time: datetime = None) -> datetime or None:
        current_time = start_time or datetime.now(tz=self.timezone).replace(microsecond=0)
        cron_expression = self._remove_minutes(cron_expression) 
        iterator = croniter(cron_expression, current_time)

        if croniter.match(cron_expression, current_time): # Check if current_time matches cron expression
            next_match = current_time
        else:
            next_match = iterator.get_next(datetime)

        if self.check_modifier(modifier, next_match):
            return next_match.astimezone(self.timezone).replace(microsecond=0) # Ensure correct timezone and reset microseconds

        for _ in range(9999):  # Limit to prevent infinite loop, reduced by 1 due to initial check
            next_match = iterator.get_next(datetime)
            if self.check_modifier(modifier, next_match):
                return next_match.astimezone(self.timezone)  # Ensure correct timezone

        return None

