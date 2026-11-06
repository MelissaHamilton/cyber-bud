"""Exercise the real Streamlit UI with fake AI responses and temporary storage."""
import sys
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

APP_DIR = Path(__file__).parents[1] / 'pydanticConvoAgent'
sys.path.insert(0, str(APP_DIR))
from src import database as db


class DailyLimitAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)
        scope = patch.object(db, 'DATA_DIR', self.data_dir)
        scope.start()
        self.addCleanup(scope.stop)
        with db.visitor_database('a' * 32):
            for _ in range(49):
                db.reserve_daily_message()
        self.app = AppTest.from_string(f'''
import sys, runpy, types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, {str(APP_DIR)!r})
import streamlit as st
from src import database as db, quiz
from components import visitor
fake = types.ModuleType('src.agent')
fake.create_agent = lambda: None
async def reply(*args):
    st.session_state.test_calls = st.session_state.get('test_calls', 0) + 1
    return 'Synthetic test answer', []
async def question(*args):
    st.session_state.test_calls = st.session_state.get('test_calls', 0) + 1
    return dict(question='Synthetic question?', options=dict(A='Yes', B='No', C='Maybe', D='Never'), correct='A', explanations=dict(A='Yes', B='No', C='No', D='No'), correct_explanation='Yes')
fake.run_agent = reply
with patch.dict(sys.modules, {{'src.agent': fake}}), patch.object(visitor, 'get_visitor_id', return_value='a' * 32), patch.object(db, 'DATA_DIR', Path({str(self.data_dir)!r})), patch.object(quiz, 'generate_quiz_question', question):
    runpy.run_path({str(APP_DIR / 'app.py')!r}, run_name='__main__')
''').run(timeout=15)
        self.assertFalse(self.app.exception)

    def button(self, label):
        return next(button for button in self.app.button if button.label == label)

    def assert_exhausted(self):
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.chat_input[0].disabled)
        self.assertIn('CyberBud’s taking a breather. Come back tomorrow!', [item.value for item in self.app.info])
        self.assertIn('0 of 50 AI messages left today in this browser', [item.value for item in self.app.caption])

    def test_last_chat_reply_then_new_session_and_reset_cannot_bypass(self):
        self.app.chat_input[0].set_value('Synthetic question').run()
        self.assertEqual(self.app.session_state.test_calls, 1)
        self.assert_exhausted()
        self.button('+ New Session').click().run()
        self.assert_exhausted()
        self.button('Reset My Data').click().run()
        self.button('Confirm').click().run()
        self.assert_exhausted()
        self.assertEqual(self.app.session_state.test_calls, 1)

    def test_last_quiz_is_answerable_but_next_question_cannot_call_ai(self):
        concept = {'id': 1, 'name': 'Synthetic concept'}
        from src.quiz import create_initial_quiz_state
        self.app.session_state.quiz_mode = True
        self.app.session_state.quiz_state = create_initial_quiz_state([concept, concept])
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.test_calls, 1)
        self.assertTrue(any(button.label == 'A) Yes' for button in self.app.button))
        self.button('A) Yes').click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.test_calls, 1)
        # Request the next question with the exhausted allowance.
        state = self.app.session_state.quiz_state
        state['loading'] = True
        state['answered'] = False
        self.app.run()
        self.assertFalse(self.app.exception)
        self.assertIn('CyberBud’s taking a breather. Come back tomorrow!', [item.value for item in self.app.info])
        self.assertEqual(self.app.session_state.test_calls, 1)
