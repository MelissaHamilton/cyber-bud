"""
Quiz module for CyberBud.
Handles multiple choice question generation and parsing.
"""

import re
from typing import Optional
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage


# Prompt template for generating multiple choice questions
QUIZ_PROMPT_TEMPLATE = """Generate a multiple choice question about "{concept}" in cybersecurity.

The question should test understanding, not just memorization. Make distractors plausible but clearly wrong to someone who understands the concept.

Format your response EXACTLY like this (include all sections):
QUESTION: [question text]
A) [option]
B) [option]
C) [option]
D) [option]
CORRECT: [A/B/C/D]
CORRECT_EXPLANATION: [why the correct answer is right - 1-2 sentences]
A_EXPLANATION: [why A is wrong OR why A is correct, depending on the answer]
B_EXPLANATION: [why B is wrong OR why B is correct, depending on the answer]
C_EXPLANATION: [why C is wrong OR why C is correct, depending on the answer]
D_EXPLANATION: [why D is wrong OR why D is correct, depending on the answer]
"""


def parse_quiz_response(response_text: str) -> Optional[dict]:
    """
    Parse the AI response into structured quiz data.

    Returns:
        dict with keys: question, options (dict A-D), correct, correct_explanation,
        wrong_explanations (dict A-D)
        Or None if parsing fails
    """
    try:
        # Extract question
        question_match = re.search(r'QUESTION:\s*(.+?)(?=\n[A-D]\))', response_text, re.DOTALL)
        if not question_match:
            return None
        question = question_match.group(1).strip()

        # Extract options A-D
        options = {}
        for letter in ['A', 'B', 'C', 'D']:
            pattern = rf'{letter}\)\s*(.+?)(?=\n[B-D]\)|CORRECT:)'
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                options[letter] = match.group(1).strip()
            else:
                # Try alternate pattern for last option
                pattern = rf'{letter}\)\s*(.+?)(?=\nCORRECT:)'
                match = re.search(pattern, response_text, re.DOTALL)
                if match:
                    options[letter] = match.group(1).strip()

        if len(options) != 4:
            return None

        # Extract correct answer
        correct_match = re.search(r'CORRECT:\s*([A-D])', response_text)
        if not correct_match:
            return None
        correct = correct_match.group(1)

        # Extract correct explanation
        correct_exp_match = re.search(r'CORRECT_EXPLANATION:\s*(.+?)(?=\n[A-D]_EXPLANATION:)', response_text, re.DOTALL)
        if not correct_exp_match:
            return None
        correct_explanation = correct_exp_match.group(1).strip()

        # Extract explanations for each option
        explanations = {}
        for letter in ['A', 'B', 'C', 'D']:
            pattern = rf'{letter}_EXPLANATION:\s*(.+?)(?=\n[B-D]_EXPLANATION:|$)'
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                explanations[letter] = match.group(1).strip()
            else:
                explanations[letter] = ""

        return {
            "question": question,
            "options": options,
            "correct": correct,
            "correct_explanation": correct_explanation,
            "explanations": explanations
        }

    except Exception:
        return None


async def generate_quiz_question(agent: Agent, concept_name: str, message_history: list[ModelMessage] = None) -> Optional[dict]:
    """
    Generate a multiple choice question for a concept.

    Args:
        agent: The Pydantic AI agent
        concept_name: Name of the concept to quiz on
        message_history: Optional conversation history

    Returns:
        Parsed quiz data dict or None if generation/parsing fails
    """
    prompt = QUIZ_PROMPT_TEMPLATE.format(concept=concept_name)

    result = await agent.run(
        prompt,
        message_history=message_history or []
    )

    parsed = parse_quiz_response(result.output)
    if parsed:
        parsed["concept_name"] = concept_name

    return parsed


def get_result_message(quiz_data: dict, user_answer: str) -> str:
    """
    Generate the result message after user answers.

    Args:
        quiz_data: The parsed quiz data
        user_answer: The letter the user selected (A, B, C, or D)

    Returns:
        Formatted result message string
    """
    correct = quiz_data["correct"]
    is_correct = user_answer == correct

    if is_correct:
        return f"""✓ Correct!

**{correct}) {quiz_data['options'][correct]}**

{quiz_data['correct_explanation']}"""
    else:
        wrong_explanation = quiz_data["explanations"].get(user_answer, "")
        correct_explanation = quiz_data["correct_explanation"]

        return f"""✗ Not quite

**You picked: {user_answer}) {quiz_data['options'][user_answer]}**
→ {wrong_explanation}

**Correct: {correct}) {quiz_data['options'][correct]}**
→ {correct_explanation}"""


def create_initial_quiz_state(concepts: list[dict]) -> dict:
    """
    Create the initial quiz state structure.

    Args:
        concepts: List of concept dicts from database

    Returns:
        Quiz state dict
    """
    return {
        "active": True,
        "concepts": concepts,
        "current_index": 0,
        "question": "",
        "options": {},
        "correct": "",
        "explanations": {},
        "correct_explanation": "",
        "user_answer": None,
        "answered": False,
        "results": [],  # Track results per concept: {"concept_id": id, "correct": bool}
        "loading": True  # True when waiting for question generation
    }
