"""
Database module for CyberBud.
Handles SQLite operations for sessions, messages, and concepts.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

# Database file location
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "cyberbud.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory for dict-like access."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Create tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Sessions table - tracks study sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            summary TEXT
        )
    """)

    # Messages table - stores conversation history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # Concepts table - tracks cybersecurity terms learned
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            times_discussed INTEGER DEFAULT 1,
            understanding_level INTEGER DEFAULT 1,
            last_reviewed_at TIMESTAMP
        )
    """)

    # Migration: Add new columns if they don't exist (for existing databases)
    cursor.execute("PRAGMA table_info(concepts)")
    columns = [col[1] for col in cursor.fetchall()]
    if "understanding_level" not in columns:
        cursor.execute("ALTER TABLE concepts ADD COLUMN understanding_level INTEGER DEFAULT 1")
    if "last_reviewed_at" not in columns:
        cursor.execute("ALTER TABLE concepts ADD COLUMN last_reviewed_at TIMESTAMP")

    # Concept mentions - links concepts to messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS concept_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            mentioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (concept_id) REFERENCES concepts(id),
            FOREIGN KEY (message_id) REFERENCES messages(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()


# --- Session Operations ---

def create_session() -> int:
    """Create a new study session and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions DEFAULT VALUES")
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id: int) -> Optional[dict]:
    """Get a session by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_sessions(limit: int = 10) -> list[dict]:
    """Get recent sessions with at least 1 message, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*,
               (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count
        FROM sessions s
        WHERE (SELECT COUNT(*) FROM messages WHERE session_id = s.id) > 0
        ORDER BY started_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session_title(session_id: int, max_length: int = 40) -> str:
    """Get a title for a session based on first user message."""
    messages = get_session_messages(session_id)
    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if len(content) > max_length:
                return content[:max_length].strip() + "..."
            return content
    return "New session"


def end_session(session_id: int, summary: Optional[str] = None):
    """Mark a session as ended."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
        (datetime.now(), summary, session_id)
    )
    conn.commit()
    conn.close()


# --- Message Operations ---

def save_message(session_id: int, role: str, content: str) -> int:
    """Save a message and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id


def get_session_messages(session_id: int) -> list[dict]:
    """Get all messages for a session, in order."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Concept Operations ---

def save_concept(name: str, category: Optional[str] = None) -> int:
    """Save a concept or increment its discussion count if it exists."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if concept exists
    cursor.execute("SELECT id, times_discussed FROM concepts WHERE name = ?", (name,))
    row = cursor.fetchone()

    if row:
        # Increment discussion count
        cursor.execute(
            "UPDATE concepts SET times_discussed = ? WHERE id = ?",
            (row["times_discussed"] + 1, row["id"])
        )
        concept_id = row["id"]
    else:
        # Insert new concept
        cursor.execute(
            "INSERT INTO concepts (name, category) VALUES (?, ?)",
            (name, category)
        )
        concept_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return concept_id


def record_concept_mention(concept_id: int, message_id: int, session_id: int):
    """Record that a concept was mentioned in a message."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO concept_mentions (concept_id, message_id, session_id) VALUES (?, ?, ?)",
        (concept_id, message_id, session_id)
    )
    conn.commit()
    conn.close()


def get_all_concepts() -> list[dict]:
    """Get all concepts, ordered by times discussed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM concepts ORDER BY times_discussed DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_concepts_by_category() -> dict[str, list[dict]]:
    """Get concepts grouped by category."""
    concepts = get_all_concepts()
    grouped = {}
    for concept in concepts:
        category = concept["category"] or "Uncategorized"
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(concept)
    return grouped


def get_concept_count() -> int:
    """Get total number of unique concepts learned."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM concepts")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def update_concept_understanding(concept_id: int, level: int):
    """Update the understanding level of a concept (1-5)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE concepts SET understanding_level = ?, last_reviewed_at = ? WHERE id = ?",
        (max(1, min(5, level)), datetime.now(), concept_id)
    )
    conn.commit()
    conn.close()


def mark_concept_reviewed(concept_id: int):
    """Mark a concept as reviewed (updates last_reviewed_at timestamp)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE concepts SET last_reviewed_at = ? WHERE id = ?",
        (datetime.now(), concept_id)
    )
    conn.commit()
    conn.close()


def get_concepts_needing_review() -> list[dict]:
    """Get concepts that need review: understanding < 3 OR not reviewed in 7+ days."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM concepts
        WHERE understanding_level < 3
           OR last_reviewed_at IS NULL
           OR last_reviewed_at < datetime('now', '-7 days')
        ORDER BY
            CASE WHEN last_reviewed_at IS NULL THEN 0 ELSE 1 END,
            understanding_level ASC,
            last_reviewed_at ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_concepts_for_quiz(limit: int = 5) -> list[dict]:
    """Get weak concepts for quiz mode, prioritizing low understanding and old reviews."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM concepts
        WHERE understanding_level < 4
           OR last_reviewed_at IS NULL
           OR last_reviewed_at < datetime('now', '-7 days')
        ORDER BY
            understanding_level ASC,
            CASE WHEN last_reviewed_at IS NULL THEN 0 ELSE 1 END,
            last_reviewed_at ASC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_concept_by_name(name: str) -> Optional[dict]:
    """Get a concept by its name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM concepts WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_session(session_id: int):
    """Delete a session and its messages/mentions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM concept_mentions WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def clear_all_data():
    """Delete all sessions, messages, concepts, and mentions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM concept_mentions")
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM concepts")
    conn.commit()
    conn.close()


# Initialize database when module is imported
init_database()
