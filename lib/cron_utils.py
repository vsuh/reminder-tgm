from croniter import croniter
from datetime import datetime, timedelta, date
import pytz
from dateutil.relativedelta import relativedelta
import re

class VCron:
    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)

    def check_cron(self, cron_expression: str, date: datetime) -> bool:
        cron_expression = self._remove_minutes(cron_expression)
        return croniter.match(cron_expression, date)

    def _remove_minutes(self, cron: str)->str:
        cron_parts = cron.split()
        cron_parts[0] = "*" 
        return " ".join(cron_parts)

    def valid(self, cron_expression: str) -> bool:
        try:
            croniter(cron_expression)  # Directly check with croniter
            return True
        except ValueError:
            return False

    def is_valid_modifier(self, modifier):
        if not modifier:
            return True
        pattern = r'^(?:(?P<date>\d{8})>?)?(?P<period>[wdm]\/\d+)$' # Added 'm' for month support

        match = re.match(pattern, modifier)
        if not match:
            return False

        period_part = match['period']

        if date_part := match['date']:
            try:
                year = int(date_part[:4])
                month = int(date_part[4:6])
                day = int(date_part[6:])

                # Проверка на корректность даты
                if not (1900 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31):
                    return False
            except ValueError:
                return False

        # Проверка периода
        period_match = re.match(r'[wdm]\/\d+$', period_part) # Added 'm' for month support
        return bool(period_match)

    def check_modifier(self, modifier: str, now: datetime) -> bool:
        now = now.replace(tzinfo=self.timezone) # Ensure now has the correct timezone
        if not modifier:
            return True

        parts = modifier.split(">")
        start_date_str = parts[0] if len(parts) == 2 else "20010101"
        rule = parts[-1]

        try:
            start_datetime = self.timezone.localize(datetime.combine(datetime.strptime(start_date_str, "%Y%m%d").date(), datetime.min.time()))
        except OverflowError:
            start_datetime = self.timezone.localize(datetime(2001, 1, 1)) # Fallback to a safe date
        except ValueError:
            return False # Invalid date format

        if rule.startswith(("w/", "d/")):  # Handle all three types
            interval = int(rule[2:])
            delta = relativedelta(now, start_datetime)
            days_since = self.days_since(now.date(), start_datetime.date(), )

            if rule.startswith("w/"):
                weeks = int(days_since/7)
                return (weeks % interval == 0) and (days_since%7 == 0)
            elif rule.startswith("d/"):
                return days_since % interval == 0

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

