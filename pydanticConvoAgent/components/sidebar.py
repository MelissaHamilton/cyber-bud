"""
Sidebar component for CyberBud.
Displays session management and learning progress.
"""

import streamlit as st
from src import database as db
from src.quiz import create_initial_quiz_state


def _render_session_row(session: dict):
    """Render a single session row in the sidebar."""
    label = session["_title"]
    is_current = (
        "session_id" in st.session_state and
        st.session_state.session_id == session["id"]
    )

    if is_current:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.button(
                label, key=f"session_{session['id']}", use_container_width=True, type="primary")
        with col2:
            st.empty()
    else:
        col1, col2 = st.columns([5, 1])
        with col1:
            if st.button(label, key=f"session_{session['id']}", use_container_width=True):
                load_session(session["id"])
                st.rerun()
        with col2:
            if st.button("🗑", key=f"del_{session['id']}", help="Delete session"):
                db.delete_session(session["id"])
                st.rerun()


def render_sidebar():
    """Render the sidebar with session management and progress."""

    # Inject CSS outside sidebar to avoid layout spacing
    st.markdown("""
        <style>
        [data-testid="stSidebar"] button[kind="primary"] {
            border: 2px solid #4CAF50;
            border-left-width: 4px;
            background-color: transparent;
            color: inherit;
        }
        [data-testid="stSidebar"] [data-testid="stColumn"]:last-child button[kind="secondary"] {
            display: flex;
            align-items: center;
            justify-content: center;
            border-color: transparent;
            background: transparent;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("CyberBud")
        st.caption("Your Cybersecurity Learning Assistant")

        st.divider()

        # --- Session Management ---
        st.subheader("Sessions")

        # New session button
        if st.button("+ New Session", use_container_width=True):
            # End current session if exists
            if "session_id" in st.session_state and st.session_state.session_id:
                db.end_session(st.session_state.session_id)

            # Create new session
            new_session_id = db.create_session()
            st.session_state.session_id = new_session_id
            st.session_state.messages = []
            st.session_state.pydantic_messages = []
            st.session_state.message_count = 0
            st.rerun()

        # Session search
        search_query = st.text_input(
            "Search sessions", placeholder="Search...", label_visibility="collapsed")

        # Recent sessions
        recent_sessions = db.get_recent_sessions(limit=20)

        if recent_sessions:
            # Filter sessions by search query
            filtered_sessions = []
            for session in recent_sessions:
                title = db.get_session_title(session["id"])
                session["_title"] = title  # Cache title for display
                if not search_query or search_query.lower() in title.lower():
                    filtered_sessions.append(session)

            if filtered_sessions:
                st.caption(f"Sessions ({len(filtered_sessions)})")
                visible = filtered_sessions[:5]
                overflow = filtered_sessions[5:]

                for session in visible:
                    _render_session_row(session)

                if overflow:
                    with st.expander(f"Show {len(overflow)} more"):
                        for session in overflow:
                            _render_session_row(session)
            elif search_query:
                st.caption("No matching sessions")

        st.divider()

        # --- Learning Progress ---
        st.subheader("Learning Progress")

        # Concept count
        concept_count = db.get_concept_count()
        st.metric("Concepts Learned", concept_count)

        # Needs review count
        needs_review = db.get_concepts_needing_review()
        needs_review_count = len(needs_review)

        if needs_review_count > 0:
            st.metric("Needs Review", needs_review_count)

        remaining = 25 - st.session_state.get("message_count", 0)
        st.caption(f"{remaining} messages remaining this session")

        # Quiz Me button
        if concept_count > 0:
            if st.button("Quiz Me on Weak Spots", use_container_width=True):
                start_quiz_mode()
                st.rerun()

        # Concepts needing attention - actionable list
        if needs_review_count > 0:
            with st.expander("Review Queue"):
                for concept in needs_review[:8]:
                    render_concept_row(concept, section="review")
                if needs_review_count > 8:
                    st.caption(f"+{needs_review_count - 8} more")

        # All concepts view
        if concept_count > 0:
            with st.expander("All Concepts"):
                concepts_by_category = db.get_concepts_by_category()
                for category, concepts in concepts_by_category.items():
                    st.markdown(f"**{category}**")
                    for concept in concepts[:5]:
                        render_concept_row(concept, section=f"all_{category}")
                    if len(concepts) > 5:
                        st.caption(f"+{len(concepts) - 5} more")

        st.divider()

        # --- Settings ---
        with st.expander("Settings"):
            st.caption("Danger Zone")
            if st.button("Reset All Data", type="secondary", use_container_width=True):
                st.session_state.confirm_reset = True

            if st.session_state.get("confirm_reset"):
                st.warning("Delete ALL sessions, messages, and concepts?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.confirm_reset = False
                        st.rerun()
                with col2:
                    if st.button("Confirm", type="primary", use_container_width=True):
                        db.clear_all_data()
                        st.session_state.session_id = db.create_session()
                        st.session_state.messages = []
                        st.session_state.pydantic_messages = []
                        st.session_state.quiz_mode = False
                        st.session_state.quiz_concepts = []
                        st.session_state.quiz_state = None
                        st.session_state.message_count = 0
                        st.session_state.confirm_reset = False
                        st.rerun()


def get_level_label(level: int) -> tuple[str, str]:
    """Get human-readable label and color for understanding level."""
    levels = {
        1: ("New", "🔴"),
        2: ("Learning", "🟡"),
        3: ("Getting it", "🟢"),
        4: ("Solid", "🔵"),
        5: ("Mastered", "⭐"),
    }
    return levels.get(level, ("New", "🔴"))


def render_concept_row(concept: dict, section: str = ""):
    """Render a single concept with level indicator and actions."""
    level = concept.get("understanding_level", 1)
    label, indicator = get_level_label(level)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"{indicator} **{concept['name']}**")
        st.caption(label)

    with col2:
        # Button to ask about this concept - unique key per section
        key = f"ask_{section}_{concept['id']}"
        quiz_active = st.session_state.get("quiz_mode", False)
        if st.button("📖", key=key, help="Ask about this", disabled=quiz_active):
            st.session_state.pending_concept_question = concept["name"]
            st.rerun()


def load_session(session_id: int):
    """Load a previous session's messages."""
    st.session_state.session_id = session_id

    # Load messages from database
    messages = db.get_session_messages(session_id)

    # Convert to display format
    st.session_state.messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
    ]

    # Clear pydantic messages (will rebuild from conversation)
    st.session_state.pydantic_messages = []
    st.session_state.message_count = 0
    st.session_state.quiz_mode = False
    st.session_state.quiz_state = None
    st.session_state.quiz_concepts = []
    st.session_state.awaiting_rating = False


def ensure_session():
    """Ensure a session exists, creating one if needed."""
    if "session_id" not in st.session_state or st.session_state.session_id is None:
        st.session_state.session_id = db.create_session()
        st.session_state.messages = []
        st.session_state.pydantic_messages = []
        st.session_state.message_count = 0


def start_quiz_mode():
    """Start quiz mode by selecting concepts to quiz on."""
    # Get 3 concepts for the quiz (one at a time flow)
    quiz_concepts = db.get_concepts_for_quiz(limit=3)

    if not quiz_concepts:
        st.session_state.quiz_mode = False
        st.session_state.quiz_concepts = []
        st.session_state.quiz_state = None
        return

    st.session_state.quiz_mode = True
    st.session_state.quiz_concepts = quiz_concepts
    st.session_state.awaiting_rating = False

    # Initialize the new quiz state
    st.session_state.quiz_state = create_initial_quiz_state(quiz_concepts)
