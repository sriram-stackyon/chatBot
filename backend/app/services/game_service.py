"""In-memory game state management for Tic Tac Toe (Project 11)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from app.schemas.game import Board, GameState, HistoryEntry, ScoreItem

# ── In-memory stores ───────────────────────────────────────────────────────────
# Key: "{user_id}:{game_id}"
_games: dict[str, GameState] = {}

# Per-user history list (most recent first)
_history: dict[str, list[HistoryEntry]] = {}

_MAX_HISTORY = 50


# ── Board helpers ──────────────────────────────────────────────────────────────

def empty_board() -> Board:
    return [["", "", ""], ["", "", ""], ["", "", ""]]


def check_winner(board: Board) -> Optional[str]:
    """Return the winning symbol ('X' or 'O') or None."""
    # Rows
    for row in board:
        if row[0] and row[0] == row[1] == row[2]:
            return row[0]
    # Columns
    for col in range(3):
        if board[0][col] and board[0][col] == board[1][col] == board[2][col]:
            return board[0][col]
    # Diagonals
    if board[1][1]:
        if board[0][0] == board[1][1] == board[2][2]:
            return board[1][1]
        if board[0][2] == board[1][1] == board[2][0]:
            return board[1][1]
    return None


def is_board_full(board: Board) -> bool:
    return all(cell != "" for row in board for cell in row)


def get_empty_cells(board: Board) -> list[tuple[int, int]]:
    return [(r, c) for r in range(3) for c in range(3) if board[r][c] == ""]


# ── Game lifecycle ─────────────────────────────────────────────────────────────

def start_game(user_id: str, difficulty: str = "medium") -> GameState:
    game_id = str(uuid.uuid4())
    state = GameState(
        game_id=game_id,
        board=empty_board(),
        current_turn="X",
        player_symbol="X",
        ai_symbol="O",
        status="ongoing",
        winner=None,
        move_count=0,
        difficulty=difficulty,
        message="Your turn! You are X.",
    )
    _games[f"{user_id}:{game_id}"] = state
    return state


def get_game(user_id: str, game_id: str) -> Optional[GameState]:
    return _games.get(f"{user_id}:{game_id}")


def save_game(user_id: str, state: GameState) -> None:
    _games[f"{user_id}:{state.game_id}"] = state


def record_history(user_id: str, state: GameState) -> None:
    if state.winner == state.player_symbol:
        result = "win"
    elif state.winner == state.ai_symbol:
        result = "loss"
    else:
        result = "draw"

    entry = HistoryEntry(
        game_id=state.game_id,
        result=result,
        moves=state.move_count,
        difficulty=state.difficulty,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    bucket = _history.setdefault(user_id, [])
    bucket.insert(0, entry)
    _history[user_id] = bucket[:_MAX_HISTORY]


def get_history(user_id: str) -> tuple[list[HistoryEntry], ScoreItem]:
    games = _history.get(user_id, [])
    wins = sum(1 for g in games if g.result == "win")
    losses = sum(1 for g in games if g.result == "loss")
    draws = sum(1 for g in games if g.result == "draw")
    return games, ScoreItem(wins=wins, losses=losses, draws=draws, total=len(games))
