"""LiteLLM-powered Tic Tac Toe AI agent (Project 11).

The agent receives the current board state and returns the best move for
the AI symbol ('O') using LLM reasoning.  A robust fallback algorithm
(win > block > centre > corners > edges) is used if the LLM fails or
returns an illegal move.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.schemas.game import Board

logger = logging.getLogger(__name__)

# ── Difficulty-aware system prompts ────────────────────────────────────────────

_SYSTEM_EASY = """\
You are a Tic Tac Toe player using symbol 'O'. The human is 'X'.
Play casually — you may occasionally miss winning moves or forget to block.
Always return ONLY valid JSON:
{"row": <0|1|2>, "col": <0|1|2>, "reason": "<short explanation>"}
The chosen cell MUST be empty (shown as ""). No extra text."""

_SYSTEM_MEDIUM = """\
You are an intelligent Tic Tac Toe AI agent. Your symbol is 'O'. The human player is 'X'.

Think step-by-step before choosing your move:
1. Can I WIN this turn? → take that cell immediately.
2. Will my opponent (X) win next turn? → BLOCK that cell.
3. Is the center (1,1) free? → take it.
4. Is a corner free? → take a corner (0,0), (0,2), (2,0), or (2,2).
5. Otherwise take any available edge.

Return ONLY valid JSON — no markdown, no extra text:
{"row": <0|1|2>, "col": <0|1|2>, "reason": "<1-2 sentence strategic explanation>"}

The chosen cell MUST be empty (""). If you break this rule the move will be rejected."""

_SYSTEM_HARD = """\
You are an unbeatable Tic Tac Toe AI agent. Your symbol is 'O'. The human is 'X'.

You MUST play perfectly — never lose. Follow this strict priority:
1. WINNING MOVE: If you can complete a row/col/diagonal, do it NOW.
2. BLOCK WIN: If X can complete a row/col/diagonal next turn, block it NOW.
3. FORK: Create or block a fork (two simultaneous threats).
4. CENTER: Take (1,1) if empty.
5. OPPOSITE CORNER: If opponent is in a corner, take the opposite corner.
6. CORNER: Take any empty corner.
7. EDGE: Take any empty edge cell.

Think thoroughly through ALL possibilities before answering.

Return ONLY this JSON — nothing else:
{"row": <0|1|2>, "col": <0|1|2>, "reason": "<precise strategic explanation>"}

The cell at (row, col) MUST currently be empty (""). Illegal moves are auto-rejected."""

_PROMPTS = {"easy": _SYSTEM_EASY, "medium": _SYSTEM_MEDIUM, "hard": _SYSTEM_HARD}

_MAX_ATTEMPTS = 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _board_to_text(board: Board) -> str:
    """Render the board in a readable format for the LLM."""
    lines = ["Current board (row 0-2, col 0-2). Empty cells shown as \".\":"]
    lines.append("       col0   col1   col2")
    for r, row in enumerate(board):
        cells = " | ".join(cell if cell else "." for cell in row)
        lines.append(f"  row{r}  {cells}")
    empty = [(r, c) for r in range(3) for c in range(3) if board[r][c] == ""]
    lines.append(f"\nAvailable moves: {', '.join(f'({r},{c})' for r, c in empty) or 'none'}")
    return "\n".join(lines)


def _check_winner_inline(board: Board) -> Optional[str]:
    for row in board:
        if row[0] and row[0] == row[1] == row[2]:
            return row[0]
    for col in range(3):
        if board[0][col] and board[0][col] == board[1][col] == board[2][col]:
            return board[0][col]
    if board[1][1]:
        if board[0][0] == board[1][1] == board[2][2]:
            return board[1][1]
        if board[0][2] == board[1][1] == board[2][0]:
            return board[1][1]
    return None


def _algorithmic_best(board: Board) -> tuple[int, int]:
    """Fallback: win → block → centre → corners → edges."""
    empty = [(r, c) for r in range(3) for c in range(3) if board[r][c] == ""]
    if not empty:
        raise ValueError("No moves available")

    for symbol in ("O", "X"):
        for r, c in empty:
            board[r][c] = symbol
            if _check_winner_inline(board):
                board[r][c] = ""
                return (r, c)
            board[r][c] = ""

    if board[1][1] == "":
        return (1, 1)
    for r, c in [(0, 0), (0, 2), (2, 0), (2, 2)]:
        if board[r][c] == "":
            return (r, c)
    return empty[0]


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some LLMs add."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content block; strip a leading "json" language tag
        inner = parts[1] if len(parts) > 1 else text
        if inner.startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return text


# ── Public API ────────────────────────────────────────────────────────────────

async def get_ai_move(board: Board, difficulty: str = "medium") -> dict:
    """
    Ask the LLM to choose the best move for 'O'.

    Returns ``{"row": int, "col": int, "reason": str}``.
    Falls back to the algorithmic best move after *_MAX_ATTEMPTS* failures.
    """
    empty = [(r, c) for r in range(3) for c in range(3) if board[r][c] == ""]
    if not empty:
        raise ValueError("No valid moves available on the board")

    system_prompt = _PROMPTS.get(difficulty, _SYSTEM_MEDIUM)
    board_text = _board_to_text(board)
    user_msg = (
        f"{board_text}\n\n"
        "It is your turn (you are 'O'). "
        "Respond with ONLY the JSON move object — no markdown, no explanation outside the JSON."
    )

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_API_BASE,
        temperature=0.1 if difficulty != "easy" else 0.6,
        max_tokens=300,
        streaming=False,
    )

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await llm.ainvoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
            )
            raw = _strip_fences(str(response.content))
            data = json.loads(raw)
            row, col = int(data["row"]), int(data["col"])

            if 0 <= row <= 2 and 0 <= col <= 2 and board[row][col] == "":
                reason = str(data.get("reason", "Strategic move")).strip()
                logger.info("LLM move (%d,%d) on attempt %d: %s", row, col, attempt, reason)
                return {"row": row, "col": col, "reason": reason}

            logger.warning(
                "LLM returned occupied/invalid cell (%d,%d) on attempt %d — retrying",
                row, col, attempt,
            )
        except Exception as exc:
            logger.warning("LLM attempt %d failed: %s", attempt, exc)

    # All LLM attempts failed — use algorithmic fallback
    logger.info("Using algorithmic fallback after %d failed LLM attempts", _MAX_ATTEMPTS)
    fb_r, fb_c = _algorithmic_best(board)
    return {
        "row": fb_r,
        "col": fb_c,
        "reason": "I carefully analyzed the board and chose the best available position.",
    }
