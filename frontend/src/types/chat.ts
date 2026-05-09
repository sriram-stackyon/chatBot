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
