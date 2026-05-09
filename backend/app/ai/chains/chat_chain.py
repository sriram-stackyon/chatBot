import logging
from pathlib import Path
from typing import AsyncIterator

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from app.ai.llm import get_chat_llm

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

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
            (
                "human",
                "Chat History:\n{history}\n\nUser Message:\n{input}\n\nAttachment Context:\n{attachment_context}\n\nRules:\nUse attachment content only if relevant\nKeep response concise",
            ),
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
    history: str,
    attachment_context: str,
) -> AsyncIterator[str]:
    """Yield streamed text chunks from the chat chain."""
    chain = get_chat_chain()
    async for chunk in chain.astream(
        {
            "input": user_input,
            "history": history,
            "attachment_context": attachment_context or "No attachment context.",
        }
    ):
        if chunk:
            yield chunk
