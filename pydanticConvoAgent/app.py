"""
CyberBud - A Cybersecurity Learning Assistant

Main Streamlit application entry point.
Run with: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
import asyncio
import nest_asyncio

from pydantic_ai.exceptions import ModelHTTPError

from src.agent import create_agent, run_agent
from src.models import extract_concepts
from src import database as db
from src.quiz import generate_quiz_question, get_result_message, create_initial_quiz_state
from components.sidebar import render_sidebar, ensure_session

MAX_MESSAGES_PER_SESSION = 25

# Allow nested async event loops (needed for Streamlit)
nest_asyncio.apply()

# Page configuration
st.set_page_config(
    page_title="CyberBud",
    page_icon="🔐",
    layout="centered"
)


@st.cache_resource
def get_agent():
    """Cache the agent instance."""
    return create_agent()


def check_message_limit() -> bool:
    """Return True if the session message limit has been reached."""
    return st.session_state.get("message_count", 0) >= MAX_MESSAGES_PER_SESSION


def increment_message_count():
    """Increment the session message counter."""
    st.session_state.message_count = st.session_state.get("message_count", 0) + 1


def _get_openai_error_code(body: object) -> str | None:
    """Extract the error code from an OpenAI error response body."""
    if isinstance(body, dict):
        error = body.get("error", {})
        if isinstance(error, dict):
            return error.get("code")
    return None


def save_and_track_message(role: str, content: str):
    """Save message to database and track any concepts mentioned."""
    session_id = st.session_state.session_id

    # Save message to database
    message_id = db.save_message(session_id, role, content)

    # Extract and track concepts from assistant responses
    if role == "assistant":
        concepts = extract_concepts(content)
        for concept_name, category in concepts:
            concept_id = db.save_concept(concept_name, category)
            db.record_concept_mention(concept_id, message_id, session_id)


def render_understanding_rating():
    """Render understanding level rating buttons after a quiz."""
    st.divider()
    st.markdown("**Rate your understanding:**")

    quiz_concepts = st.session_state.quiz_concepts
    concept_names = ", ".join([c["name"] for c in quiz_concepts[:3]])
    if len(quiz_concepts) > 3:
        concept_names += f", +{len(quiz_concepts) - 3} more"
    st.caption(f"Concepts: {concept_names}")

    # Rating buttons - clear labels
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔴 Still fuzzy", key="rating_1", use_container_width=True):
            update_quiz_understanding(1)
            st.rerun()

    with col2:
        if st.button("🟡 Getting it", key="rating_3", use_container_width=True):
            update_quiz_understanding(3)
            st.rerun()

    with col3:
        if st.button("🟢 Got it!", key="rating_5", use_container_width=True):
            update_quiz_understanding(5)
            st.rerun()


def update_quiz_understanding(level: int):
    """Update understanding level for all quiz concepts."""
    for concept in st.session_state.quiz_concepts:
        db.update_concept_understanding(concept["id"], level)

    # Reset quiz mode
    st.session_state.quiz_mode = False
    st.session_state.quiz_concepts = []
    st.session_state.awaiting_rating = False
    st.session_state.quiz_state = None


def init_quiz_state():
    """Initialize quiz-related session state variables."""
    if "quiz_mode" not in st.session_state:
        st.session_state.quiz_mode = False
    if "quiz_concepts" not in st.session_state:
        st.session_state.quiz_concepts = []
    if "awaiting_rating" not in st.session_state:
        st.session_state.awaiting_rating = False
    if "quiz_state" not in st.session_state:
        st.session_state.quiz_state = None


def render_quiz_header():
    """Render the quiz header showing current concept and progress."""
    quiz_state = st.session_state.quiz_state
    if not quiz_state:
        return

    current_idx = quiz_state["current_index"]
    total = len(quiz_state["concepts"])
    concept_name = quiz_state["concepts"][current_idx]["name"]

    st.markdown(f"### Quiz: {concept_name} ({current_idx + 1} of {total})")


def render_quiz_question(agent):
    """Render the current quiz question with answer buttons."""
    quiz_state = st.session_state.quiz_state
    if not quiz_state:
        return

    # Check message limit before generating a question
    if check_message_limit():
        st.warning(
            f"You've reached the {MAX_MESSAGES_PER_SESSION}-message limit for this session. "
            "Start a new session to continue quizzing."
        )
        st.session_state.quiz_mode = False
        st.session_state.quiz_state = None
        return

    # Check if we need to generate a question
    if quiz_state["loading"]:
        current_concept = quiz_state["concepts"][quiz_state["current_index"]]
        with st.spinner(f"Generating question about {current_concept['name']}..."):
            try:
                loop = asyncio.get_event_loop()
                quiz_data = loop.run_until_complete(
                    generate_quiz_question(agent, current_concept["name"])
                )
            except ModelHTTPError as e:
                error_code = _get_openai_error_code(e.body)
                if error_code in ("insufficient_quota", "billing_hard_limit_reached"):
                    st.warning("CyberBud has reached its usage limit. Please try again another day.")
                elif e.status_code == 429:
                    st.warning("CyberBud is getting too many requests right now. Please wait a minute and try again.")
                else:
                    st.error("Something went wrong with the AI service. Please try again in a moment.")
                st.session_state.quiz_mode = False
                st.session_state.quiz_state = None
                return
            except Exception:
                st.error("Something went wrong generating the quiz. Please try again.")
                st.session_state.quiz_mode = False
                st.session_state.quiz_state = None
                return

            if quiz_data:
                increment_message_count()
                quiz_state["question"] = quiz_data["question"]
                quiz_state["options"] = quiz_data["options"]
                quiz_state["correct"] = quiz_data["correct"]
                quiz_state["explanations"] = quiz_data["explanations"]
                quiz_state["correct_explanation"] = quiz_data["correct_explanation"]
                quiz_state["loading"] = False
                st.rerun()
            else:
                st.error("Failed to generate question. Skipping this concept.")
                advance_quiz()
                st.rerun()
        return

    # Show the question
    st.markdown(f"**{quiz_state['question']}**")
    st.write("")  # Spacing

    # Show answer buttons
    for letter in ['A', 'B', 'C', 'D']:
        option_text = quiz_state["options"].get(letter, "")
        if st.button(
            f"{letter}) {option_text}",
            key=f"quiz_option_{letter}",
            use_container_width=True
        ):
            quiz_state["user_answer"] = letter
            quiz_state["answered"] = True

            # Record result
            current_concept = quiz_state["concepts"][quiz_state["current_index"]]
            quiz_state["results"].append({
                "concept_id": current_concept["id"],
                "correct": letter == quiz_state["correct"]
            })

            st.rerun()


def render_quiz_result():
    """Render the result after user answers a question."""
    quiz_state = st.session_state.quiz_state
    if not quiz_state or not quiz_state["answered"]:
        return

    user_answer = quiz_state["user_answer"]
    is_correct = user_answer == quiz_state["correct"]

    # Result header
    if is_correct:
        st.success("✓ Correct!")
    else:
        st.error("✗ Not quite")

    # Build result message
    correct = quiz_state["correct"]
    if is_correct:
        st.markdown(f"**{correct}) {quiz_state['options'][correct]}**")
        st.markdown(quiz_state["correct_explanation"])
    else:
        st.markdown(f"**You picked: {user_answer}) {quiz_state['options'][user_answer]}**")
        wrong_exp = quiz_state["explanations"].get(user_answer, "")
        if wrong_exp:
            st.markdown(f"→ {wrong_exp}")

        st.write("")
        st.markdown(f"**Correct: {correct}) {quiz_state['options'][correct]}**")
        st.markdown(f"→ {quiz_state['correct_explanation']}")

    st.write("")  # Spacing

    # Navigation buttons
    current_idx = quiz_state["current_index"]
    total = len(quiz_state["concepts"])
    is_last = current_idx >= total - 1

    col1, col2 = st.columns(2)
    with col1:
        if not is_last:
            if st.button("Next Question →", use_container_width=True):
                advance_quiz()
                st.rerun()
    with col2:
        if st.button("Done" if is_last else "End Quiz", use_container_width=True):
            finish_quiz()
            st.rerun()


def advance_quiz():
    """Move to the next question in the quiz."""
    quiz_state = st.session_state.quiz_state
    if not quiz_state:
        return

    quiz_state["current_index"] += 1
    quiz_state["question"] = ""
    quiz_state["options"] = {}
    quiz_state["correct"] = ""
    quiz_state["explanations"] = {}
    quiz_state["correct_explanation"] = ""
    quiz_state["user_answer"] = None
    quiz_state["answered"] = False
    quiz_state["loading"] = True


def finish_quiz():
    """End the quiz and show rating UI."""
    st.session_state.awaiting_rating = True


def main():
    # Render sidebar (sessions, progress)
    render_sidebar()

    # Ensure we have an active session
    ensure_session()

    # Get the agent
    agent = get_agent()

    # Main chat area
    st.title("CyberBud")

    # Initialize message lists if needed
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pydantic_messages" not in st.session_state:
        st.session_state.pydantic_messages = []
    if "message_count" not in st.session_state:
        st.session_state.message_count = 0

    # Initialize quiz state
    init_quiz_state()

    # Check if we're in active quiz mode with quiz_state
    quiz_active = (
        st.session_state.quiz_mode and
        st.session_state.quiz_state is not None and
        st.session_state.quiz_state.get("active", False)
    )

    if quiz_active and not st.session_state.awaiting_rating:
        # Render quiz UI
        render_quiz_header()

        quiz_state = st.session_state.quiz_state
        if quiz_state["answered"]:
            render_quiz_result()
        else:
            render_quiz_question(agent)

    elif st.session_state.quiz_mode and st.session_state.awaiting_rating:
        # Show understanding rating after quiz completion
        st.markdown("### Quiz Complete!")

        # Show summary
        quiz_state = st.session_state.quiz_state
        if quiz_state and quiz_state["results"]:
            correct_count = sum(1 for r in quiz_state["results"] if r["correct"])
            total = len(quiz_state["results"])
            st.markdown(f"**Score: {correct_count} / {total}**")

        render_understanding_rating()

    else:
        # Normal chat mode
        st.caption("Ask me anything about cybersecurity!")

        # Display previous messages
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if check_message_limit():
            st.info(
                f"You've reached the {MAX_MESSAGES_PER_SESSION}-message limit for this session. "
                "Start a new session from the sidebar to keep chatting."
            )
            st.chat_input("Message limit reached", disabled=True)
        else:
            # Handle pending concept question (from sidebar "ask about this")
            if "pending_concept_question" in st.session_state and st.session_state.pending_concept_question:
                concept_name = st.session_state.pending_concept_question
                st.session_state.pending_concept_question = None
                user_input = f"Explain {concept_name} to me. What is it, why does it matter in cybersecurity, and give me an example."
                process_user_input(agent, user_input)
                st.rerun()

            # Handle user input
            if user_input := st.chat_input("What would you like to learn about?"):
                process_user_input(agent, user_input)
                st.rerun()


def process_user_input(agent, user_input: str):
    """Process user input and get AI response."""
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Add to display messages
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Save to database
    save_and_track_message("user", user_input)

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                loop = asyncio.get_event_loop()
                response_text, new_messages = loop.run_until_complete(
                    run_agent(agent, user_input, st.session_state.pydantic_messages)
                )
            except ModelHTTPError as e:
                error_code = _get_openai_error_code(e.body)
                if error_code in ("insufficient_quota", "billing_hard_limit_reached"):
                    st.warning("CyberBud has reached its usage limit. Please try again another day.")
                elif e.status_code == 429:
                    st.warning("CyberBud is getting too many requests right now. Please wait a minute and try again.")
                else:
                    st.error("Something went wrong with the AI service. Please try again in a moment.")
                return
            except Exception:
                st.error("Something went wrong. Please try again.")
                return

            # Update pydantic message history
            st.session_state.pydantic_messages.extend(new_messages)

        # Display response
        st.markdown(response_text)

    # Count only on success
    increment_message_count()

    # Add to display messages
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # Save to database and track concepts
    save_and_track_message("assistant", response_text)


if __name__ == "__main__":
    main()
