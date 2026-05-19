import { useCallback, useEffect, useRef, useState } from 'react';
import {
  GameBoard,
  GameDifficulty,
  GameHistoryEntry,
  GameScore,
  GameState,
  GameStatus,
} from '../types/chat';
import { getGameHistory, makeGameMove, restartGame, startGame } from '../lib/api';

// ── Props ──────────────────────────────────────────────────────────────────────

interface Props {
  accessToken: string;
  userEmail: string;
  onBack: () => void;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const EMPTY_BOARD: GameBoard = [
  ['', '', ''],
  ['', '', ''],
  ['', '', ''],
];

const WINNING_LINES = [
  [[0, 0], [0, 1], [0, 2]],
  [[1, 0], [1, 1], [1, 2]],
  [[2, 0], [2, 1], [2, 2]],
  [[0, 0], [1, 0], [2, 0]],
  [[0, 1], [1, 1], [2, 1]],
  [[0, 2], [1, 2], [2, 2]],
  [[0, 0], [1, 1], [2, 2]],
  [[0, 2], [1, 1], [2, 0]],
];

function getWinningCells(board: GameBoard): Set<string> {
  for (const line of WINNING_LINES) {
    const [a, b, c] = line;
    const va = board[a[0]][a[1]];
    if (va && va === board[b[0]][b[1]] && va === board[c[0]][c[1]]) {
      return new Set(line.map(([r, col]) => `${r}-${col}`));
    }
  }
  return new Set();
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function DifficultyBadge({ difficulty }: { difficulty: GameDifficulty }) {
  const map: Record<GameDifficulty, { label: string; cls: string }> = {
    easy: { label: 'Easy', cls: 'ttt-badge-easy' },
    medium: { label: 'Medium', cls: 'ttt-badge-medium' },
    hard: { label: 'Hard', cls: 'ttt-badge-hard' },
  };
  const { label, cls } = map[difficulty];
  return <span className={`ttt-badge ${cls}`}>{label}</span>;
}

function StatusBanner({ status, message }: { status: GameStatus | null; message: string }) {
  if (!status || status === 'ongoing') {
    return <p className="ttt-status-msg">{message}</p>;
  }
  const map: Record<string, { cls: string; icon: string }> = {
    player_wins: { cls: 'ttt-status-win', icon: '🏆' },
    ai_wins: { cls: 'ttt-status-loss', icon: '🤖' },
    draw: { cls: 'ttt-status-draw', icon: '🤝' },
  };
  const cfg = map[status] ?? { cls: '', icon: '' };
  return (
    <div className={`ttt-result-banner ${cfg.cls}`}>
      <span className="ttt-result-icon">{cfg.icon}</span>
      <span>{message}</span>
    </div>
  );
}

function Cell({
  value,
  row,
  col,
  isWinning,
  isAiLast,
  disabled,
  onClick,
}: {
  value: string;
  row: number;
  col: number;
  isWinning: boolean;
  isAiLast: boolean;
  disabled: boolean;
  onClick: (r: number, c: number) => void;
}) {
  const cls = [
    'ttt-cell',
    value === 'X' ? 'ttt-cell-x' : value === 'O' ? 'ttt-cell-o' : '',
    isWinning ? 'ttt-cell-winning' : '',
    isAiLast ? 'ttt-cell-ai-last' : '',
    !value && !disabled ? 'ttt-cell-empty' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={cls}
      onClick={() => onClick(row, col)}
      disabled={disabled || !!value}
      aria-label={`Cell ${row},${col}${value ? ` (${value})` : ' (empty)'}`}
    >
      {value && <span className="ttt-symbol">{value}</span>}
    </button>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export function TicTacToePage({ accessToken, userEmail, onBack }: Props) {
  const [gameId, setGameId] = useState<string | null>(null);
  const [board, setBoard] = useState<GameBoard>(EMPTY_BOARD);
  const [status, setStatus] = useState<GameStatus>('ongoing');
  const [message, setMessage] = useState('Select a difficulty and start a new game!');
  const [aiMove, setAiMove] = useState<{ row: number; col: number; reason: string } | null>(null);
  const [aiThinking, setAiThinking] = useState(false);
  const [difficulty, setDifficulty] = useState<GameDifficulty>('medium');
  const [score, setScore] = useState<GameScore>({ wins: 0, losses: 0, draws: 0, total: 0 });
  const [history, setHistory] = useState<GameHistoryEntry[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [playerSymbol] = useState('X');

  const winningCells = getWinningCells(board);

  // ── Load history on mount ────────────────────────────────────────────────────

  useEffect(() => {
    getGameHistory(accessToken)
      .then((data) => {
        setHistory(data.games);
        setScore(data.score);
      })
      .catch(() => {/* silently ignore */});
  }, [accessToken]);

  // ── Refresh history / score after game ends ──────────────────────────────────

  const refreshHistory = useCallback(() => {
    getGameHistory(accessToken)
      .then((data) => {
        setHistory(data.games);
        setScore(data.score);
      })
      .catch(() => {});
  }, [accessToken]);

  // ── Apply response from backend ─────────────────────────────────────────────

  function applyGameState(state: GameState) {
    setGameId(state.game_id);
    setBoard(state.board as GameBoard);
    setStatus(state.status as GameStatus);
    setMessage(state.message);
    setAiMove(state.ai_move ?? null);
  }

  // ── Start / Restart ──────────────────────────────────────────────────────────

  async function handleStart() {
    setError(null);
    setStarting(true);
    setAiMove(null);
    try {
      const state = gameId
        ? await restartGame(accessToken, difficulty)
        : await startGame(accessToken, difficulty);
      applyGameState(state);
      if (gameId) refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start game');
    } finally {
      setStarting(false);
    }
  }

  // ── Player move ──────────────────────────────────────────────────────────────

  async function handleCellClick(row: number, col: number) {
    if (!gameId || status !== 'ongoing' || aiThinking || board[row][col]) return;
    setError(null);
    setAiThinking(true);
    setAiMove(null);
    try {
      const state = await makeGameMove(accessToken, gameId, row, col);
      applyGameState(state);
      if (state.status !== 'ongoing') refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Move failed');
    } finally {
      setAiThinking(false);
    }
  }

  // ── Turn indicator ───────────────────────────────────────────────────────────

  const isPlayerTurn = gameId && status === 'ongoing' && !aiThinking;

  return (
    <div className="ttt-page">
      {/* Top bar */}
      <header className="ttt-topbar">
        <button className="ttt-back-btn" onClick={onBack} aria-label="Back to chat">
          ← Chat
        </button>
        <div className="ttt-topbar-title">
          <span className="ttt-topbar-icon">🎮</span>
          <span>AI Tic Tac Toe</span>
        </div>
        <span className="ttt-topbar-user">{userEmail}</span>
      </header>

      <div className="ttt-body">
        {/* Left: game area */}
        <main className="ttt-main">
          {/* Controls row */}
          <div className="ttt-controls">
            <div className="ttt-difficulty-group">
              <span className="ttt-control-label">Difficulty</span>
              {(['easy', 'medium', 'hard'] as GameDifficulty[]).map((d) => (
                <button
                  key={d}
                  className={`ttt-diff-btn ${difficulty === d ? 'ttt-diff-btn-active' : ''}`}
                  onClick={() => setDifficulty(d)}
                  disabled={aiThinking}
                >
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
            <button
              className="ttt-start-btn"
              onClick={handleStart}
              disabled={starting || aiThinking}
            >
              {starting ? 'Starting…' : gameId ? '↺ Restart' : '▶ New Game'}
            </button>
          </div>

          {/* Error */}
          {error && <div className="ttt-error">{error}</div>}

          {/* Status banner */}
          <StatusBanner status={status} message={message} />

          {/* Turn indicator */}
          {gameId && status === 'ongoing' && (
            <div className="ttt-turn-row">
              {aiThinking ? (
                <span className="ttt-thinking">
                  <span className="ttt-thinking-dots" />
                  AI is thinking…
                </span>
              ) : (
                <span className="ttt-your-turn">Your turn — click a cell</span>
              )}
            </div>
          )}

          {/* Board */}
          <div
            className={`ttt-board ${!gameId ? 'ttt-board-disabled' : ''} ${aiThinking ? 'ttt-board-thinking' : ''}`}
          >
            {board.map((row, r) =>
              row.map((cell, c) => (
                <Cell
                  key={`${r}-${c}`}
                  value={cell}
                  row={r}
                  col={c}
                  isWinning={winningCells.has(`${r}-${c}`)}
                  isAiLast={!!(aiMove && aiMove.row === r && aiMove.col === c)}
                  disabled={!isPlayerTurn}
                  onClick={handleCellClick}
                />
              ))
            )}
          </div>

          {/* AI reasoning */}
          {aiMove && (
            <div className="ttt-ai-reason">
              <span className="ttt-ai-reason-label">🤖 AI reasoning:</span>
              <span className="ttt-ai-reason-text">{aiMove.reason}</span>
            </div>
          )}

          {/* Legend */}
          <div className="ttt-legend">
            <span className="ttt-legend-x">You = X</span>
            <span className="ttt-legend-sep">·</span>
            <span className="ttt-legend-o">AI = O</span>
          </div>
        </main>

        {/* Right: scoreboard + history */}
        <aside className="ttt-sidebar">
          {/* Scoreboard */}
          <div className="ttt-scoreboard">
            <h3 className="ttt-section-title">Scoreboard</h3>
            <div className="ttt-score-grid">
              <div className="ttt-score-card ttt-score-win">
                <span className="ttt-score-num">{score.wins}</span>
                <span className="ttt-score-label">Wins</span>
              </div>
              <div className="ttt-score-card ttt-score-loss">
                <span className="ttt-score-num">{score.losses}</span>
                <span className="ttt-score-label">Losses</span>
              </div>
              <div className="ttt-score-card ttt-score-draw">
                <span className="ttt-score-num">{score.draws}</span>
                <span className="ttt-score-label">Draws</span>
              </div>
            </div>
            {score.total > 0 && (
              <p className="ttt-score-total">
                Win rate:{' '}
                <strong>{Math.round((score.wins / score.total) * 100)}%</strong> from{' '}
                {score.total} game{score.total !== 1 ? 's' : ''}
              </p>
            )}
          </div>

          {/* Current difficulty */}
          {gameId && (
            <div className="ttt-current-diff">
              <span className="ttt-control-label">Current:</span>{' '}
              <DifficultyBadge difficulty={difficulty} />
            </div>
          )}

          {/* History toggle */}
          <div className="ttt-history-section">
            <button
              className="ttt-history-toggle"
              onClick={() => setHistoryOpen((o) => !o)}
            >
              {historyOpen ? '▲' : '▼'} Game History ({history.length})
            </button>
            {historyOpen && (
              <ul className="ttt-history-list">
                {history.length === 0 && (
                  <li className="ttt-history-empty">No games played yet.</li>
                )}
                {history.map((g, i) => (
                  <li key={g.game_id} className={`ttt-history-item ttt-history-${g.result}`}>
                    <span className="ttt-hist-num">#{i + 1}</span>
                    <span className="ttt-hist-result">
                      {g.result === 'win' ? '🏆 Win' : g.result === 'loss' ? '❌ Loss' : '🤝 Draw'}
                    </span>
                    <span className="ttt-hist-meta">
                      {g.moves} moves · {g.difficulty}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* How to play */}
          <div className="ttt-how-to">
            <h4 className="ttt-section-title">How to Play</h4>
            <ul className="ttt-tips">
              <li>You are <strong>X</strong>, AI is <strong>O</strong></li>
              <li>Click any empty cell on your turn</li>
              <li>Get 3 in a row to win</li>
              <li><em>Easy</em> — AI plays casually</li>
              <li><em>Medium</em> — AI plays strategically</li>
              <li><em>Hard</em> — AI plays perfectly</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default TicTacToePage;
