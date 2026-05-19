from typing import Any

import pandas as pd
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

from app.core.config import settings


def _build_agent_prefix() -> str:
    return (
        "You are a read-only data analysis assistant for tabular datasets. "
        "Answer the user question concisely and accurately from the provided DataFrame only. "
        "Do not fabricate columns or rows. "
        "Do not perform any write operations, file operations, network access, or unsafe actions. "
        "If the answer cannot be derived from the data, clearly say so in one concise sentence."
    )


def create_sheets_dataframe_agent(df: pd.DataFrame) -> Any:
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_API_BASE,
        temperature=0,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=False,
    )

    return create_pandas_dataframe_agent(
        llm=llm,
        df=df,
        agent_type="tool-calling",
        verbose=False,
        return_intermediate_steps=True,
        allow_dangerous_code=True,  # required for pandas DataFrame agent to function
        prefix=_build_agent_prefix(),
    )
