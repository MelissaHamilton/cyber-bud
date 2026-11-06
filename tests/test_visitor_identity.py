"""Identity readiness and in-memory history isolation; no AI/network calls."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'pydanticConvoAgent'))
from components import visitor


class StopRendering(Exception):
    pass


class VisitorIdentityTests(unittest.TestCase):
    def resolve(self, token, state):
        ui = SimpleNamespace(session_state=state, caption=Mock(), error=Mock(),
                             stop=Mock(side_effect=StopRendering))
        with patch.object(visitor, 'st', ui), patch.object(visitor, '_browser_identity', return_value=token):
            return visitor.get_visitor_id()

    def test_pending_or_invalid_identity_stops_before_opening_storage(self):
        for token in (None, {}, {'error': 'cookies_unavailable'}, 'bad', 'a' * 32):
            with self.subTest(token=token), self.assertRaises(StopRendering):
                self.resolve(token, {})

    def test_first_identity_clears_cached_shared_history(self):
        state = {'messages': ['legacy shared message'], 'session_id': 1,
                 'cyberbud_browser_identity': 'component state'}
        owner = self.resolve('a' * 64, state)
        self.assertEqual(state, {'_progress_owner': owner, 'cyberbud_browser_identity': 'component state'})
        self.assertEqual(len(owner), 32)
        self.assertNotEqual(owner, 'a' * 32)

    def test_returning_identity_preserves_its_own_active_chat(self):
        owner = visitor.visitor_id_from_token('a' * 64)
        state = {'_progress_owner': owner, 'messages': ['my message']}
        self.assertEqual(self.resolve('a' * 64, state), owner)
        self.assertEqual(state['messages'], ['my message'])

    def test_changed_identity_cannot_keep_previous_cached_chat(self):
        state = {'_progress_owner': visitor.visitor_id_from_token('a' * 64),
                 'messages': ['previous visitor message']}
        self.resolve('b' * 64, state)
        self.assertNotIn('messages', state)
