"""FastAPI routes for Project 11 — AI Agent Powered Tic Tac Toe Game."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.agents.tic_tac_toe_agent import get_ai_move
from app.api.deps import get_current_user
from app.schemas.auth import AuthUser
from app.schemas.game import (
    AiMoveInfo,
    GameHistoryResponse,
    MoveRequest,
    MoveResponse,
    RestartResponse,
    StartGameRequest,
    StartGameResponse,
)
from app.services import game_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["game"])


# ── POST /game/start ──────────────────────────────────────────────────────────

@router.post("/game/start", response_model=StartGameResponse)
async def start_game(
    request: StartGameRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> StartGameResponse:
    """Start a new Tic Tac Toe game. The player is always 'X', AI is 'O'."""
    state = game_service.start_game(current_user.user_id, request.difficulty)
    return StartGameResponse(
        game_id=state.game_id,
        board=state.board,
        current_turn=state.current_turn,
        player_symbol=state.player_symbol,
        status=state.status,
        message=state.message,
    )


# ── POST /game/move ───────────────────────────────────────────────────────────

@router.post("/game/move", response_model=MoveResponse)
async def make_move(
    request: MoveRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> MoveResponse:
    """
    Apply the player's move, then let the AI respond.

    Returns the updated board, game status, and the AI's move details.
    """
    state = game_service.get_game(current_user.user_id, request.game_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    if state.status != "ongoing":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Game is already finished")
    if state.current_turn != state.player_symbol:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not your turn")

    row, col = request.row, request.col
    if state.board[row][col] != "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cell is already occupied")

    # ── Apply player move ──────────────────────────────────────────────────────
    state.board[row][col] = state.player_symbol
    state.move_count += 1

    winner = game_service.check_winner(state.board)
    if winner:
        state.status = "player_wins"
        state.winner = winner
        state.current_turn = ""
        state.message = "You win! Congratulations! The AI is impressed."
        game_service.record_history(current_user.user_id, state)
        game_service.save_game(current_user.user_id, state)
        return MoveResponse(
            game_id=state.game_id,
            board=state.board,
            current_turn=state.current_turn,
            status=state.status,
            winner=state.winner,
            ai_move=None,
            message=state.message,
        )

    if game_service.is_board_full(state.board):
        state.status = "draw"
        state.winner = None
        state.current_turn = ""
        state.message = "It's a draw! Well played!"
        game_service.record_history(current_user.user_id, state)
        game_service.save_game(current_user.user_id, state)
        return MoveResponse(
            game_id=state.game_id,
            board=state.board,
            current_turn=state.current_turn,
            status=state.status,
            winner=None,
            ai_move=None,
            message=state.message,
        )

    # ── AI's turn ──────────────────────────────────────────────────────────────
    state.current_turn = state.ai_symbol
    try:
        ai_result = await get_ai_move(state.board, state.difficulty)
    except Exception as exc:
        logger.exception("AI agent failed to produce a move")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI agent error: {exc}",
        ) from exc

    ai_row, ai_col = ai_result["row"], ai_result["col"]
    state.board[ai_row][ai_col] = state.ai_symbol
    state.move_count += 1
    ai_move_info = AiMoveInfo(row=ai_row, col=ai_col, reason=ai_result["reason"])

    winner = game_service.check_winner(state.board)
    if winner:
        state.status = "ai_wins"
        state.winner = winner
        state.current_turn = ""
        state.message = f"AI wins! {ai_result['reason']}"
        game_service.record_history(current_user.user_id, state)
    elif game_service.is_board_full(state.board):
        state.status = "draw"
        state.winner = None
        state.current_turn = ""
        state.message = "It's a draw! Great game!"
        game_service.record_history(current_user.user_id, state)
    else:
        state.current_turn = state.player_symbol
        state.message = f"AI played ({ai_row},{ai_col}). Your turn!"

    game_service.save_game(current_user.user_id, state)
    return MoveResponse(
        game_id=state.game_id,
        board=state.board,
        current_turn=state.current_turn,
        status=state.status,
        winner=state.winner,
        ai_move=ai_move_info,
        message=state.message,
    )


# ── POST /game/restart ────────────────────────────────────────────────────────

@router.post("/game/restart", response_model=RestartResponse)
async def restart_game(
    request: StartGameRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> RestartResponse:
    """Start a fresh game (same as /game/start — creates a new game_id)."""
    state = game_service.start_game(current_user.user_id, request.difficulty)
    return RestartResponse(
        game_id=state.game_id,
        board=state.board,
        current_turn=state.current_turn,
        player_symbol=state.player_symbol,
        status=state.status,
        message=state.message,
    )


# ── GET /game/history ─────────────────────────────────────────────────────────

@router.get("/game/history", response_model=GameHistoryResponse)
async def game_history(
    current_user: AuthUser = Depends(get_current_user),
) -> GameHistoryResponse:
    """Return the authenticated user's game history and score totals."""
    games, score = game_service.get_history(current_user.user_id)
    return GameHistoryResponse(games=games, score=score)
