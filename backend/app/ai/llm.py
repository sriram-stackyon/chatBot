import logging
from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_chat_llm() -> ChatOpenAI:
    """Return a cached LangChain LLM singleton backed by the LiteLLM proxy."""
    logger.info(
        "Initialising LLM via LiteLLM proxy: model=%s url=%s",
        settings.LLM_MODEL,
        settings.LLM_API_BASE,
    )
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_API_BASE,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,
    )
