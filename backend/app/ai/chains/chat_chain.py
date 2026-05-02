import logging
from pathlib import Path
from typing import AsyncIterator

import yaml
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from app.ai.llm import get_chat_llm

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Module-level chain — built once on first use
_chat_chain: Runnable | None = None


def _load_system_prompt() -> str:
    prompt_file = _PROMPTS_DIR / "chat.yaml"
    with open(prompt_file, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data["system"].strip()


def _build_chain() -> Runnable:
    system_prompt = _load_system_prompt()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ]
    )
    llm = get_chat_llm()
    return prompt | llm | StrOutputParser()


def get_chat_chain() -> Runnable:
    global _chat_chain
    if _chat_chain is None:
        _chat_chain = _build_chain()
        logger.info("Chat LCEL chain initialised")
    return _chat_chain


async def stream_chat_response(
    user_input: str,
    history: list[BaseMessage],
) -> AsyncIterator[str]:
    """Yield streamed text chunks from the chat chain."""
    chain = get_chat_chain()
    async for chunk in chain.astream({"input": user_input, "history": history}):
        if chunk:
            yield chunk
