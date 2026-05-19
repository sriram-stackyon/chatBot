"""Pydantic schemas for Project 11 — AI Agent Powered Tic Tac Toe Game."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# A 3×3 board where each cell is "" (empty), "X", or "O"
Board = List[List[str]]


class StartGameRequest(BaseModel):
    difficulty: str = Field("medium", pattern="^(easy|medium|hard)$")


class AiMoveInfo(BaseModel):
    row: int
    col: int
    reason: str


class GameState(BaseModel):
    game_id: str
    board: Board
    current_turn: str  # "X" or "O"
    player_symbol: str = "X"
    ai_symbol: str = "O"
    status: str  # "ongoing" | "player_wins" | "ai_wins" | "draw"
    winner: Optional[str] = None
    move_count: int = 0
    difficulty: str = "medium"
    message: str = ""


class StartGameResponse(BaseModel):
    game_id: str
    board: Board
    current_turn: str
    player_symbol: str
    status: str
    message: str


class MoveRequest(BaseModel):
    game_id: str
    row: int = Field(..., ge=0, le=2)
    col: int = Field(..., ge=0, le=2)


class MoveResponse(BaseModel):
    game_id: str
    board: Board
    current_turn: str
    status: str
    winner: Optional[str]
    ai_move: Optional[AiMoveInfo]
    message: str


class RestartResponse(BaseModel):
    game_id: str
    board: Board
    current_turn: str
    player_symbol: str
    status: str
    message: str


class ScoreItem(BaseModel):
    wins: int
    losses: int
    draws: int
    total: int


class HistoryEntry(BaseModel):
    game_id: str
    result: str  # "win" | "loss" | "draw"
    moves: int
    difficulty: str
    created_at: str


class GameHistoryResponse(BaseModel):
    games: List[HistoryEntry]
    score: ScoreItem
