# Cybersecurity Learning Assistant

An AI-powered learning assistant for cybersecurity education, built with Streamlit and Pydantic AI.

## Features
- Interactive Q&A with an AI agent specialized in cybersecurity
- Built-in quizzes with spaced repetition
- Topic categorization across 10+ cybersecurity domains

## Tech Stack
- Streamlit
- Pydantic AI
- OpenAI GPT-4o

## Live Demo
[Try it here](https://cyber-learning-assistant.streamlit.app/)

## Local Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Security Features
- Rate limiting per session
- Project-level budget caps
- Secure API key management

## Visitor progress

CyberBud stores each browser's sessions, concepts, quiz history, and ratings in a separate SQLite database. A random first-party cookie remembers the browser for one year; it is never placed in URLs. New browsers start empty. Clearing cookies, using a private window, or changing browser profiles creates a fresh workspace. People sharing a browser profile share its progress; this is anonymous browser persistence, not account authentication.

The app waits for browser identity before reading any progress. Reset and delete actions apply only to that visitor. The previous shared `pydanticConvoAgent/data/cyberbud.db` is left untouched and is never automatically assigned to a visitor because it has no ownership information. New databases live under the ignored `data/visitors/` directory. Progress lasts only while the host retains these files; durable storage across Streamlit host replacements would require an external database.

Run the isolation checks without API credentials or AI calls:

```bash
python -m unittest discover -s tests -v
node --test tests/test_browser_identity.mjs
```

The Python checks require Streamlit from the app's existing requirements. Browser checks use Node's built-in test runner and add no packages.
