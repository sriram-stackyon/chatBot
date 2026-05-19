export type MessageRole = 'user' | 'assistant';
export type AttachmentType =
  | 'pdf'
  | 'table'
  | 'text'
  | 'code'
  | 'image'
  | 'video'
  | 'generated_image'
  | 'other';

export interface Attachment {
  id: string;
  threadId: string;
  messageId?: string | null;
  originalFilename: string;
  storedFilename: string;
  storagePath: string;
  publicUrl?: string | null;
  imageUrl?: string | null;
  promptUsed?: string | null;
  mimeType: string;
  fileSize: number;
  attachmentType: AttachmentType;
  createdAt: Date;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  intermediateSql?: string | null;
  timestamp: Date;
  attachments?: Attachment[];
  isStreaming?: boolean;
}

export interface Thread {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatRequest {
  thread_id: string;
  message: string;
  history: Array<{ role: MessageRole; content: string }>;
  attachment_ids: string[];
}

export interface SQLChatRequest {
  message: string;
}

export interface SQLChatResponse {
  content: string;
  intermediate_sql?: string | null;
}

export interface SheetSourceMetadata {
  columns: string[];
  row_count: number;
}

export interface SheetQueryResponse {
  content: string;
  intermediate_steps?: string[] | null;
  preview_rows?: Record<string, unknown>[] | null;
  source_metadata: SheetSourceMetadata;
}

export interface SheetPreviewResponse {
  columns: string[];
  row_count: number;
  preview_rows: Record<string, unknown>[];
  source_name: string;
}

export interface SheetUploadResponse {
  file_path: string;
  source_type: string;
  original_filename: string;
}

export interface ApiChatAttachment {
  id: string;
  thread_id: string;
  message_id?: string | null;
  original_filename: string;
  stored_filename: string;
  storage_path: string;
  public_url?: string | null;
  image_url?: string | null;
  prompt_used?: string | null;
  mime_type: string;
  file_size: number;
  attachment_type: AttachmentType;
  created_at: string;
}

export interface ApiChatThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ApiChatMessage {
  id: string;
  thread_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  attachments?: ApiChatAttachment[];
}

export interface UploadAttachmentsResponse {
  attachments: ApiChatAttachment[];
}

export interface AuthUser {
  id: string;
  email: string | null;
}

export type ChatStatus = 'idle' | 'loading' | 'streaming' | 'error';

// ── Research Digest Agent (Project 10) ────────────────────────────────────────

export interface ArxivPaper {
  title: string;
  authors: string[];
  summary: string;
  published: string;
  arxiv_url: string;
  pdf_url: string;
  arxiv_id: string;
}

export interface ResearchStreamEvent {
  type: 'status' | 'papers' | 'chunk' | 'done' | 'error';
  message?: string;
  papers?: ArxivPaper[];
  text?: string;
}

// ── Tic Tac Toe Game (Project 11) ─────────────────────────────────────────────

export type GameCell = 'X' | 'O' | '';
export type GameBoard = GameCell[][];
export type GameStatus = 'ongoing' | 'player_wins' | 'ai_wins' | 'draw';
export type GameDifficulty = 'easy' | 'medium' | 'hard';

export interface AiMoveInfo {
  row: number;
  col: number;
  reason: string;
}

export interface GameState {
  game_id: string;
  board: GameBoard;
  current_turn: string;
  player_symbol: string;
  status: GameStatus;
  winner: string | null;
  ai_move: AiMoveInfo | null;
  message: string;
}

export interface GameHistoryEntry {
  game_id: string;
  result: 'win' | 'loss' | 'draw';
  moves: number;
  difficulty: string;
  created_at: string;
}

export interface GameScore {
  wins: number;
  losses: number;
  draws: number;
  total: number;
}

export interface GameHistoryResponse {
  games: GameHistoryEntry[];
  score: GameScore;
}
