/**
 * Centralized API client abstraction.
 * All browser network calls must live here.
 */

import {
  ApiChatAttachment,
  ApiChatMessage,
  ApiChatThread,
  ArxivPaper,
  AuthUser,
  GameDifficulty,
  GameHistoryResponse,
  GameState,
  ResearchStreamEvent,
  SheetPreviewResponse,
  SheetQueryResponse,
  SheetUploadResponse,
  SQLChatResponse,
  UploadAttachmentsResponse,
} from '../types/chat';

const env = import.meta.env as Record<string, string | undefined>;

const API_BASE = (env.VITE_API_BASE_URL ?? env.API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 1_000;

interface StreamChatOptions {
  token: string;
  threadId: string;
  message: string;
  attachmentIds?: string[];
  onChunk: (chunk: string) => void;
  onDone: () => void;
  onError: (error: Error) => void;
  signal?: AbortSignal;
}

const IMAGE_INTENT_REGEX =
  /\b(generate|create|make|draw|design)\b.{0,40}\b(image|picture|photo|art|illustration|poster|logo|wallpaper)\b|\b(image|picture|photo)\b.{0,20}\b(of|for)\b/i;

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export function isLikelyImageGenerationPrompt(message: string): boolean {
  return IMAGE_INTENT_REGEX.test(message.trim());
}

export function buildGoogleLoginUrl(nextPath = '/auth/google/callback'): string {
  const params = new URLSearchParams({ next: nextPath });
  return `${API_BASE}/api/auth/google/login?${params.toString()}`;
}

function buildHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

function buildAuthHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  };
}

async function parseError(response: Response): Promise<Error> {
  const text = await response.text();
  if (!text) {
    return new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  function toReadableMessage(value: unknown): string | null {
    if (typeof value === 'string' && value.trim()) return value;

    if (Array.isArray(value)) {
      const parts = value
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object') {
            const msg = (item as { msg?: unknown }).msg;
            const loc = (item as { loc?: unknown }).loc;
            if (typeof msg === 'string' && Array.isArray(loc)) {
              return `${loc.join('.')}: ${msg}`;
            }
            if (typeof msg === 'string') return msg;
          }
          return null;
        })
        .filter((part): part is string => Boolean(part && part.trim()));
      return parts.length > 0 ? parts.join('; ') : null;
    }

    if (value && typeof value === 'object') {
      const obj = value as Record<string, unknown>;
      const nested = toReadableMessage(obj.detail ?? obj.message ?? obj.error);
      if (nested) return nested;

      try {
        return JSON.stringify(obj);
      } catch {
        return null;
      }
    }

    return null;
  }

  try {
    const parsed = JSON.parse(text) as unknown;
    const message = toReadableMessage(parsed);
    if (message) {
      return new Error(message);
    }
  } catch {
    // Fall back to plain text body.
  }

  return new Error(text);
}

export async function signUp(
  email: string,
  password: string,
  fullName?: string,
): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/api/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName?.trim() || null }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as AuthResponse;
}

export async function signIn(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as AuthResponse;
}

export async function getMe(token: string): Promise<AuthUser> {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    headers: buildHeaders(token),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as AuthUser;
}

export async function getThreads(token: string): Promise<ApiChatThread[]> {
  const response = await fetch(`${API_BASE}/api/threads`, {
    headers: buildHeaders(token),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ApiChatThread[];
}

export async function createThread(token: string, title = 'New Chat'): Promise<ApiChatThread> {
  const response = await fetch(`${API_BASE}/api/threads`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ApiChatThread;
}

export async function renameThread(
  token: string,
  threadId: string,
  title: string,
): Promise<ApiChatThread> {
  const attempts: Array<{ method: 'PATCH' | 'PUT' | 'POST'; path: string }> = [
    { method: 'PATCH', path: `/api/threads/${threadId}` },
    { method: 'PUT', path: `/api/threads/${threadId}` },
    { method: 'POST', path: `/api/threads/${threadId}/rename` },
  ];

  let lastError: Error | null = null;
  for (const attempt of attempts) {
    const response = await fetch(`${API_BASE}${attempt.path}`, {
      method: attempt.method,
      headers: buildHeaders(token),
      body: JSON.stringify({ title }),
    });

    if (response.ok) {
      return (await response.json()) as ApiChatThread;
    }

    if (response.status === 405) {
      continue;
    }

    lastError = await parseError(response);
    break;
  }

  throw lastError ?? new Error('Rename thread failed: method not allowed by server');
}

export async function getThreadMessages(token: string, threadId: string): Promise<ApiChatMessage[]> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}/messages`, {
    headers: buildHeaders(token),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ApiChatMessage[];
}

export async function deleteThread(token: string, threadId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/threads/${threadId}`, {
    method: 'DELETE',
    headers: buildHeaders(token),
  });
  if (!response.ok) throw await parseError(response);
}

export async function querySqlChat(token: string, message: string): Promise<SQLChatResponse> {
  const response = await fetch(`${API_BASE}/api/sql/chat`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ message }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as SQLChatResponse;
}

export async function querySheetChat(
  token: string,
  question: string,
  sourceType: string,
  sourceValue: string,
): Promise<SheetQueryResponse> {
  const response = await fetch(`${API_BASE}/api/sheets/query`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ question, source_type: sourceType, source_value: sourceValue }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as SheetQueryResponse;
}

export async function previewSheet(
  token: string,
  sourceType: string,
  sourceValue: string,
): Promise<SheetPreviewResponse> {
  const response = await fetch(`${API_BASE}/api/sheets/preview`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ source_type: sourceType, source_value: sourceValue }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as SheetPreviewResponse;
}

export async function uploadSheetFile(
  token: string,
  file: File,
): Promise<SheetUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/api/sheets/upload`, {
    method: 'POST',
    headers: buildAuthHeaders(token),
    body: formData,
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as SheetUploadResponse;
}

export async function uploadAttachments(
  token: string,
  threadId: string,
  files: File[],
): Promise<ApiChatAttachment[]> {
  const formData = new FormData();
  formData.append('thread_id', threadId);
  for (const file of files) {
    formData.append('files', file);
  }

  const response = await fetch(`${API_BASE}/api/chat/attachments/upload`, {
    method: 'POST',
    headers: buildAuthHeaders(token),
    body: formData,
  });
  if (!response.ok) throw await parseError(response);
  const payload = (await response.json()) as UploadAttachmentsResponse;
  return payload.attachments;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Research Digest Agent (Project 10) ────────────────────────────────────────

export interface StreamResearchOptions {
  token: string;
  query: string;
  maxPapers?: number;
  conversationHistory?: Array<{ role: string; content: string }>;
  onStatus: (message: string) => void;
  onPapers: (papers: ArxivPaper[]) => void;
  onChunk: (text: string) => void;
  onDone: () => void;
  onError: (err: Error) => void;
  signal?: AbortSignal;
}

export async function streamResearch(options: StreamResearchOptions): Promise<void> {
  const {
    token,
    query,
    maxPapers = 12,
    conversationHistory = [],
    onStatus,
    onPapers,
    onChunk,
    onDone,
    onError,
    signal,
  } = options;

  try {
    const response = await fetch(`${API_BASE}/api/research/query`, {
      method: 'POST',
      headers: buildHeaders(token),
      body: JSON.stringify({
        query,
        max_papers: maxPapers,
        conversation_history: conversationHistory,
      }),
      signal,
    });

    if (!response.ok) {
      throw await parseError(response);
    }
    if (!response.body) throw new Error('Empty response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (!payload) continue;

        let event: ResearchStreamEvent;
        try {
          event = JSON.parse(payload) as ResearchStreamEvent;
        } catch {
          continue;
        }

        if (event.type === 'status' && event.message) {
          onStatus(event.message);
        } else if (event.type === 'papers' && event.papers) {
          onPapers(event.papers);
        } else if (event.type === 'chunk' && event.text) {
          onChunk(event.text);
        } else if (event.type === 'done') {
          onDone();
          return;
        } else if (event.type === 'error') {
          onError(new Error(event.message ?? 'Research failed'));
          return;
        }
      }
    }

    onDone();
  } catch (err) {
    if (signal?.aborted) {
      onDone();
      return;
    }
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const { token, threadId, message, attachmentIds = [], onChunk, onDone, onError, signal } = options;
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: buildHeaders(token),
        body: JSON.stringify({ thread_id: threadId, message, attachment_ids: attachmentIds }),
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Empty response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6);

          if (payload === '[DONE]') {
            onDone();
            return;
          }

          if (payload.startsWith('[ERROR]')) {
            let messageText = payload.slice(8).trim();
            try {
              const parsed = JSON.parse(messageText) as { error?: string };
              messageText = parsed.error ?? messageText;
            } catch {
              // keep raw message
            }
            throw new Error(messageText);
          }

          onChunk(payload.replace(/\\n/g, '\n'));
        }
      }

      onDone();
      return;
    } catch (error) {
      if (signal?.aborted) {
        onDone();
        return;
      }

      lastError = error instanceof Error ? error : new Error(String(error));
      if (attempt >= MAX_RETRIES) {
        onError(lastError);
        return;
      }

      await sleep(RETRY_BASE_DELAY_MS * attempt);
    }
  }

  onError(lastError ?? new Error('Unknown streaming error'));
}

// ── Tic Tac Toe Game API (Project 11) ─────────────────────────────────────────

export async function startGame(token: string, difficulty: GameDifficulty = 'medium'): Promise<GameState> {
  const res = await fetch(`${API_BASE}/api/game/start`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ difficulty }),
  });
  if (!res.ok) throw new Error(`Start game failed: ${await res.text()}`);
  return res.json() as Promise<GameState>;
}

export async function makeGameMove(
  token: string,
  game_id: string,
  row: number,
  col: number,
): Promise<GameState> {
  const res = await fetch(`${API_BASE}/api/game/move`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ game_id, row, col }),
  });
  if (!res.ok) throw new Error(`Move failed: ${await res.text()}`);
  return res.json() as Promise<GameState>;
}

export async function restartGame(token: string, difficulty: GameDifficulty = 'medium'): Promise<GameState> {
  const res = await fetch(`${API_BASE}/api/game/restart`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({ difficulty }),
  });
  if (!res.ok) throw new Error(`Restart failed: ${await res.text()}`);
  return res.json() as Promise<GameState>;
}

export async function getGameHistory(token: string): Promise<GameHistoryResponse> {
  const res = await fetch(`${API_BASE}/api/game/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`History failed: ${await res.text()}`);
  return res.json() as Promise<GameHistoryResponse>;
}

