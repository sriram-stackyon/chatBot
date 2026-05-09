from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.schemas.chat import Message


def build_message_history(history: list[Message]) -> list[BaseMessage]:
    """Convert API chat history schema to LangChain message objects."""
    lc_messages: list[BaseMessage] = []
    for msg in history:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
    return lc_messages


def format_history_for_prompt(history: list[Message]) -> str:
    if not history:
        return "No prior chat history."

    lines: list[str] = []
    for msg in history:
        speaker = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{speaker}: {msg.content}")
    return "\n\n".join(lines)
