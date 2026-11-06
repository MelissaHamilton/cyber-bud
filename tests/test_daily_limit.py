"""Per-browser daily budget regressions; no AI/network calls."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'pydanticConvoAgent'))
from src import database as db

A, B = 'a' * 32, 'b' * 32


class DailyLimitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        scope = patch.object(db, 'DATA_DIR', Path(temp.name))
        scope.start()
        self.addCleanup(scope.stop)

    def test_fifty_requests_then_blocked_even_after_new_session_and_return(self):
        with db.visitor_database(A):
            self.assertEqual(db.get_daily_messages_remaining(), 50)
            self.assertTrue(all(db.reserve_daily_message() for _ in range(50)))
            self.assertFalse(db.reserve_daily_message())
            db.create_session()
            self.assertEqual(db.get_daily_messages_remaining(), 0)
        with db.visitor_database(A):
            self.assertFalse(db.reserve_daily_message())

    def test_other_browser_has_its_own_allowance(self):
        with db.visitor_database(A):
            for _ in range(50):
                db.reserve_daily_message()
        with db.visitor_database(B):
            self.assertEqual(db.get_daily_messages_remaining(), 50)
            self.assertTrue(db.reserve_daily_message())
        with db.visitor_database(A):
            self.assertEqual(db.get_daily_messages_remaining(), 0)

    def test_delete_and_reset_study_data_cannot_restore_allowance(self):
        with db.visitor_database(A):
            db.reserve_daily_message()
            session = db.create_session()
            db.save_message(session, 'user', 'Synthetic message')
            db.delete_session(session)
            db.clear_all_data()
            self.assertEqual(db.get_daily_messages_remaining(), 49)

    def test_new_day_has_fresh_allowance(self):
        with db.visitor_database(A), patch.object(db, '_usage_day', return_value='2026-11-05'):
            for _ in range(50):
                db.reserve_daily_message()
        with db.visitor_database(A), patch.object(db, '_usage_day', return_value='2026-11-06'):
            self.assertEqual(db.get_daily_messages_remaining(), 50)
            self.assertTrue(db.reserve_daily_message())
            self.assertEqual(db.get_daily_messages_remaining(), 49)

    def test_day_changes_at_midnight_pacific_in_both_summer_and_winter(self):
        for hour, month in [(7, 7), (8, 11)]:
            for minute, expected in [(0, f'2026-{month:02}-06'), (-1, f'2026-{month:02}-05')]:
                instant = datetime(2026, month, 6, hour, tzinfo=timezone.utc) + timedelta(minutes=minute)
                with self.subTest(instant=instant), patch.object(db, 'datetime') as clock:
                    clock.now.side_effect = lambda zone: instant.astimezone(zone)
                    self.assertEqual(db._usage_day(), expected)

    def test_simultaneous_tabs_cannot_exceed_fifty(self):
        with db.visitor_database(A):
            pass  # Initialize before opening concurrent tabs.
        def request(_):
            with db.visitor_database(A):
                return db.reserve_daily_message()
        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(request, range(80)))
        self.assertEqual(sum(accepted), 50)
        with db.visitor_database(A):
            self.assertEqual(db.get_daily_messages_remaining(), 0)
