"""Privacy regressions, using synthetic data and no AI/network calls."""
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "pydanticConvoAgent"))
from src import database as db

A, B = "a" * 32, "b" * 32


class VisitorIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(db, "DATA_DIR", Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def seed(self, visitor, count=8):
        with db.visitor_database(visitor):
            session = db.create_session()
            message = db.save_message(session, "user", f"Private message for {visitor}")
            for index in range(count):
                concept = db.save_concept(f"Concept {index}", "Synthetic")
                db.record_concept_mention(concept, message, session)
            return session

    def test_new_visitor_sees_no_existing_progress_or_history(self):
        session = self.seed(A)
        with db.visitor_database(B):
            self.assertEqual(db.get_concept_count(), 0)
            self.assertEqual(db.get_recent_sessions(), [])
            self.assertEqual(db.get_session_messages(session), [])
            self.assertIsNone(db.get_session(session))
            self.assertEqual(db.get_concepts_needing_review(), [])
            self.assertEqual(db.get_concepts_for_quiz(), [])
        with db.visitor_database(A):
            self.assertEqual(db.get_concept_count(), 8)
            self.assertIn(A, db.get_session_messages(session)[0]["content"])

    def test_same_visitor_can_return_to_their_progress(self):
        session = self.seed(A)
        with db.visitor_database(A):
            self.assertEqual(db.get_concept_count(), 8)
            self.assertEqual(db.get_recent_sessions()[0]["id"], session)

    def test_reset_delete_and_ratings_do_not_affect_another_visitor(self):
        a_session = self.seed(A)
        b_session = self.seed(B)
        with db.visitor_database(B):
            concept = db.get_concept_by_name("Concept 0")
            db.update_concept_understanding(concept["id"], 5)
            db.delete_session(b_session)
            db.clear_all_data()
            self.assertEqual(db.get_concept_count(), 0)
        with db.visitor_database(A):
            self.assertEqual(db.get_concept_count(), 8)
            self.assertEqual(len(db.get_session_messages(a_session)), 1)
            self.assertEqual(db.get_concept_by_name("Concept 0")["understanding_level"], 1)

    def test_legacy_shared_database_is_not_read_or_changed(self):
        legacy = db.DATA_DIR / "cyberbud.db"
        with sqlite3.connect(legacy) as conn:
            conn.execute("CREATE TABLE private_legacy_data (value TEXT)")
            conn.execute("INSERT INTO private_legacy_data VALUES ('original progress')")
        before = legacy.read_bytes()
        self.seed(A)
        with db.visitor_database(B):
            self.assertEqual(db.get_concept_count(), 0)
            db.clear_all_data()
        self.assertEqual(legacy.read_bytes(), before)

    def test_no_unscoped_access_and_no_path_traversal(self):
        with self.assertRaises(RuntimeError):
            db.get_concept_count()
        for invalid in [None, "", "../cyberbud", "a/b", "A" * 32]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                with db.visitor_database(invalid):
                    self.fail("Invalid visitor scope was accepted")

    def test_nested_scopes_restore_the_original_visitor(self):
        self.seed(A)
        with db.visitor_database(A):
            with db.visitor_database(B):
                self.assertEqual(db.get_concept_count(), 0)
            self.assertEqual(db.get_concept_count(), 8)
        with self.assertRaises(RuntimeError):
            db.get_concept_count()

    def test_concurrent_visitors_do_not_share_database_context(self):
        barrier = threading.Barrier(2)
        def visit(visitor):
            with db.visitor_database(visitor):
                db.save_concept(visitor)
                barrier.wait(timeout=5)
                return [c["name"] for c in db.get_all_concepts()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            a, b = pool.map(visit, [A, B])
        self.assertEqual(a, [A])
        self.assertEqual(b, [B])


if __name__ == "__main__":
    unittest.main()
