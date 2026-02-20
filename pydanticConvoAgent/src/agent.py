"""
AI Agent module for CyberBud.
Configures the Pydantic AI agent with cybersecurity learning focus.
"""

import os
import streamlit as st
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage


# Ensure API key is available
openai_api_key = st.secrets["OPENAI_API_KEY"]
os.environ['OPENAI_API_KEY'] = openai_api_key

# Suppress Logfire warning
os.environ['LOGFIRE_IGNORE_NO_CONFIG'] = '1'

# System prompt - direct and practical
SYSTEM_PROMPT = """You are CyberBud, a cybersecurity learning tool.

Be direct and concise. No fluff, no motivational phrases, no "you're doing great" - just useful information.

When explaining concepts:
1. **Define it** - Plain terms first, then technical definition
2. **Why it matters** - Real-world relevance in security work
3. **How it works** - Technical details appropriate to the question
4. **Related concepts** - List 2-3 terms to explore next

Guidelines:
- Use analogies only when they genuinely clarify something
- Include practical examples from real security scenarios
- Don't pad responses with encouragement or filler
- End with the content, not with offers to help more"""


def create_agent() -> Agent:
    """Create and return the CyberBud agent."""
    return Agent(
        model='openai:gpt-4o',
        system_prompt=SYSTEM_PROMPT
    )


async def run_agent(
    agent: Agent,
    user_input: str,
    message_history: list[ModelMessage]
) -> tuple[str, list[ModelMessage]]:
    """
    Run the agent with user input and conversation history.

    Args:
        agent: The Pydantic AI agent
        user_input: The user's message
        message_history: Previous messages in the conversation

    Returns:
        Tuple of (response_text, new_messages)
    """
    result = await agent.run(
        user_input,
        message_history=message_history
    )
    return result.output, result.new_messages()
