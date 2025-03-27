import unittest
from datetime import datetime, date

import pytz
from lib.cron_utils import VCron

class TestVCron(unittest.TestCase):

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.timezone_name = "Europe/Moscow"
        self.vcron = VCron(self.timezone_name)

    def test_check_cron_true(self):
        """Тест check_cron с совпадением."""
        tz = pytz.timezone(self.timezone_name)
        date = tz.localize(datetime(2024, 3, 28, 14, 10))
        self.assertTrue(self.vcron.check_cron("* * * * *", date))

    def test_check_cron_false(self):
        """Тест check_cron без совпадения."""
        tz = pytz.timezone(self.timezone_name)
        date = tz.localize(datetime(2024, 3, 29, 10, 10))
        self.assertFalse(self.vcron.check_cron("0 14 * * *", date))

    def test_valid_cron_true(self):
        """Тест valid с корректным cron."""
        self.assertTrue(self.vcron.valid("* * * * *"))

    def test_valid_cron_false(self):
        """Тест valid с некорректным cron."""
        self.assertFalse(self.vcron.valid("* * * *"))

    def test_is_valid_modifier_true(self):
        """Тест is_valid_modifier с корректным modifier."""
        self.assertTrue(self.vcron.is_valid_modifier("20240301>d/3"))

    def test_is_valid_modifier_false(self):
        """Тест is_valid_modifier с некорректным modifier."""
        self.assertFalse(self.vcron.is_valid_modifier("20240301>d/"))

    def test_check_modifier_true(self):
        """Тест check_modifier с совпадением."""
        tz = pytz.timezone(self.timezone_name)
        now = tz.localize(datetime(2025, 3, 28, 14, 10))
        self.assertTrue(self.vcron.check_modifier("20240327>d/1", now))

    def test_check_modifier_false(self):
        """Тест check_modifier без совпадения."""
        tz = pytz.timezone(self.timezone_name)
        now = tz.localize(datetime(2024, 3, 28, 14, 10))
        self.assertFalse(self.vcron.check_modifier("20240327>d/2", now))

    def test_days_since(self):
        """Тест days_since."""
        today_date = date(2024, 3, 28)
        base_date = date(2024, 3, 27)
        self.assertEqual(self.vcron.days_since(today_date, base_date), 1)

    def test_get_next_match(self):
        """Тест get_next_match."""
        tz = pytz.timezone(self.timezone_name)
        start_time = tz.localize(datetime(2024, 3, 28, 14, 10))
        next_match = self.vcron.get_next_match("* * * * *", start_time=start_time)
        self.assertEqual(next_match.replace(tzinfo=None, microsecond=0), start_time.replace(tzinfo=None, microsecond=0))


