"""Chat orchestration service for PsyHelper LLM responses.

This module intentionally has no Streamlit dependency: callers pass all user,
profile, wellness, API key and policy data explicitly.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_groq import ChatGroq

from services.llm_prompt_service import build_llm_system_prompt

CHAT_MODEL_NAME = "llama-3.1-8b-instant"
CHAT_TEMPERATURE = 0.50
DEFAULT_SESSION_ID = "psyhelper_user"


@dataclass(frozen=True)
class ChatContext:
    profile: Mapping[str, Any]
    wellness: Mapping[str, Any]
    username: str
    user_input: str


@dataclass(frozen=True)
class ChatResponse:
    content: str


def create_chat_model(api_key):
    """Create the configured Groq chat model used by PsyHelper."""
    return ChatGroq(model=CHAT_MODEL_NAME, temperature=CHAT_TEMPERATURE, api_key=api_key)


def build_system_prompt(context, copyright_policy):
    """Build the minimized PsyHelper system prompt for a chat context."""
    return build_llm_system_prompt(context.profile, context.wellness, copyright_policy)


def build_chat_prompt(context, copyright_policy):
    """Build the complete chat prompt template used by the response chain."""
    return ChatPromptTemplate.from_messages([
        ("system", build_system_prompt(context, copyright_policy)),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])


def build_chat_chain(context, copyright_policy, chat_model):
    """Build the LLM chain with PsyHelper's prompt and model."""
    return build_chat_prompt(context, copyright_policy) | chat_model


def build_chain_with_history(chain):
    """Wrap the chain with the current empty-history behavior."""
    return RunnableWithMessageHistory(
        chain,
        lambda _session_id: ChatMessageHistory(),
        input_messages_key="input",
        history_messages_key="history",
    )


def get_response(context, api_key, copyright_policy, chat_model=None, session_id=DEFAULT_SESSION_ID):
    """Return a PsyHelper chat response using explicit context and configuration."""
    model = chat_model or create_chat_model(api_key)
    chain = build_chat_chain(context, copyright_policy, model)
    chain_with_history = build_chain_with_history(chain)
    response = chain_with_history.invoke(
        {"input": context.user_input},
        config={"configurable": {"session_id": session_id}},
    )
    return ChatResponse(content=response.content)
