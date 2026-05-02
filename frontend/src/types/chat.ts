export type MessageRole = 'user' | 'assistant';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
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
}

export interface AuthUser {
  id: string;
  email: string | null;
}

export type ChatStatus = 'idle' | 'loading' | 'streaming' | 'error';
