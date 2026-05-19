import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';

import { InputBar } from '../components/chat/InputBar';
import { MessageList } from '../components/chat/MessageList';
import ThreadSidebar from '../components/chat/ThreadSidebar';
import {
  createThread,
  deleteThread,
  getThreadMessages,
  getThreads,
  isLikelyImageGenerationPrompt,
  querySheetChat,
  querySqlChat,
  renameThread,
  streamChat,
  uploadAttachments,
} from '../lib/api';
import { ApiChatAttachment, ChatStatus, Message, SheetQueryResponse, Thread } from '../types/chat';

interface ChatPageProps {
  accessToken: string;
  userEmail: string;
  onSignOut: () => Promise<void>;
  onOpenSheetAgent: () => void;
  onOpenResearchAgent: () => void;
  onOpenTicTacToe: () => void;
}

function toThreadModel(item: {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}): Thread {
  return {
    id: item.id,
    title: item.title,
    messages: [],
    createdAt: new Date(item.created_at),
    updatedAt: new Date(item.updated_at),
  };
}

function toAttachmentModel(item: ApiChatAttachment) {
  return {
    id: item.id,
    threadId: item.thread_id,
    messageId: item.message_id ?? null,
    originalFilename: item.original_filename,
    storedFilename: item.stored_filename,
    storagePath: item.storage_path,
    publicUrl: item.public_url ?? null,
    imageUrl: item.image_url ?? null,
    promptUsed: item.prompt_used ?? null,
    mimeType: item.mime_type,
    fileSize: item.file_size,
    attachmentType: item.attachment_type,
    createdAt: new Date(item.created_at),
  };
}

function toMessageModel(item: {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  attachments?: ApiChatAttachment[];
}): Message {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    timestamp: new Date(item.created_at),
    attachments: (item.attachments ?? []).map(toAttachmentModel),
  };
}

export function ChatPage({ accessToken, userEmail, onSignOut, onOpenSheetAgent, onOpenResearchAgent, onOpenTicTacToe }: ChatPageProps) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadThreads = useCallback(async () => {
    const data = await getThreads(accessToken);
    const mapped = data.map(toThreadModel);
    setThreads(mapped);
    return mapped;
  }, [accessToken]);

  const loadMessages = useCallback(
    async (threadId: string) => {
      const data = await getThreadMessages(accessToken, threadId);
      setMessages(data.slice(-100).map(toMessageModel));
    },
    [accessToken],
  );

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      try {
        setError(null);
        const list = await loadThreads();
        if (!active) return;

        if (list.length > 0) {
          setActiveThreadId(list[0].id);
          await loadMessages(list[0].id);
        } else {
          setActiveThreadId(null);
          setMessages([]);
        }
      } catch (err) {
        const text = err instanceof Error ? err.message : String(err);
        if (active) setError(text);
      }
    }

    void bootstrap();

    return () => {
      active = false;
    };
  }, [loadMessages, loadThreads]);

  const handleNewThread = useCallback(async () => {
    try {
      setError(null);
      const created = await createThread(accessToken, 'New Chat');
      const mapped = toThreadModel(created);
      setThreads((prev) => [mapped, ...prev]);
      setActiveThreadId(mapped.id);
      setMessages([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [accessToken]);

  const handleSelectThread = useCallback(
    async (id: string) => {
      try {
        setError(null);
        setActiveThreadId(id);
        await loadMessages(id);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [loadMessages],
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      try {
        setError(null);
        await deleteThread(accessToken, threadId);

        const remainingThreads = await loadThreads();
        if (remainingThreads.length === 0) {
          setActiveThreadId(null);
          setMessages([]);
          return;
        }

        const nextThreadId =
          activeThreadId === threadId ? remainingThreads[0].id : activeThreadId ?? remainingThreads[0].id;
        setActiveThreadId(nextThreadId);
        await loadMessages(nextThreadId);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [accessToken, activeThreadId, loadMessages, loadThreads],
  );

  const handleRenameThread = useCallback(
    async (threadId: string, title: string) => {
      try {
        setError(null);
        const updated = await renameThread(accessToken, threadId, title);
        setThreads((prev) =>
          prev
            .map((thread) =>
              thread.id === threadId
                ? {
                    ...thread,
                    title: updated.title,
                    updatedAt: new Date(updated.updated_at),
                  }
                : thread,
            )
            .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [accessToken],
  );

  const handleSend = useCallback(
    async (content: string, files: File[]) => {
      const trimmed = content.trim();
      if (!trimmed || status === 'loading' || status === 'streaming') return;

      try {
        setError(null);
        setStatus('loading');

        let threadId = activeThreadId;
        if (!threadId) {
          const created = await createThread(accessToken, (trimmed || 'New Chat').slice(0, 80));
          const mapped = toThreadModel(created);
          setThreads((prev) => [mapped, ...prev]);
          setActiveThreadId(mapped.id);
          threadId = mapped.id;
        }

        const uploadedAttachments = files.length > 0 ? await uploadAttachments(accessToken, threadId, files) : [];
        const sqlCommandPrefix = '/sql';
        const isSqlQuery = trimmed.toLowerCase().startsWith(`${sqlCommandPrefix} `);
        const sqlQuestion = isSqlQuery ? trimmed.slice(sqlCommandPrefix.length).trim() : '';

        const sheetCommandPrefix = '/sheet';
        const isSheetQuery = trimmed.toLowerCase().startsWith(`${sheetCommandPrefix} `);
        const sheetArgs = isSheetQuery ? trimmed.slice(sheetCommandPrefix.length).trim() : '';
        // Split on first whitespace (space or newline) — first token is source, rest is question
        const sheetTokenMatch = sheetArgs.match(/^(\S+)\s+([\s\S]+)$/);
        const sheetSource = sheetTokenMatch ? sheetTokenMatch[1].trim() : sheetArgs.trim();
        const sheetQuestion = sheetTokenMatch ? sheetTokenMatch[2].trim() : '';
        function detectSourceType(value: string): string {
          if (value.includes('docs.google.com/spreadsheets')) return 'gsheet';
          if (value.toLowerCase().endsWith('.xlsx')) return 'xlsx';
          return 'csv';
        }

        const userMessage: Message = {
          id: uuidv4(),
          role: 'user',
          content: trimmed,
          timestamp: new Date(),
          attachments: uploadedAttachments.map(toAttachmentModel),
        };

        const assistantTempId = uuidv4();
        const isImagePrompt = isLikelyImageGenerationPrompt(trimmed);
        const assistantTemp: Message = {
          id: assistantTempId,
          role: 'assistant',
          content: isImagePrompt ? 'Generating image from your prompt...' : '',
          timestamp: new Date(),
          isStreaming: true,
        };

        setMessages((prev) => [...prev, userMessage, assistantTemp]);

        if (isSqlQuery) {
          if (!sqlQuestion) {
            throw new Error('Please provide a SQL question after /sql.');
          }

          const sqlResponse = await querySqlChat(accessToken, sqlQuestion);
          setStatus('idle');
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantTempId
                ? {
                    ...msg,
                    content: sqlResponse.content,
                    intermediateSql: sqlResponse.intermediate_sql ?? null,
                    isStreaming: false,
                  }
                : msg,
            ),
          );

          setThreads((prev) =>
            prev.map((t) => (t.id === threadId ? { ...t, updatedAt: new Date() } : t)),
          );
          return;
        }

        if (isSheetQuery) {
          if (!sheetSource || !sheetQuestion) {
            throw new Error('Usage: /sheet <url_or_filepath> <question>');
          }
          const sourceType = detectSourceType(sheetSource);
          const sheetResponse: SheetQueryResponse = await querySheetChat(
            accessToken,
            sheetQuestion,
            sourceType,
            sheetSource,
          );

          const sheetContent = sheetResponse.content;

          setStatus('idle');
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantTempId
                ? { ...msg, content: sheetContent, isStreaming: false }
                : msg,
            ),
          );
          setThreads((prev) =>
            prev.map((t) => (t.id === threadId ? { ...t, updatedAt: new Date() } : t)),
          );
          return;
        }

        abortRef.current = new AbortController();
        let streamFailure: Error | null = null;

        await streamChat({
          token: accessToken,
          threadId,
          message: trimmed,
          attachmentIds: uploadedAttachments.map((attachment) => attachment.id),
          signal: abortRef.current.signal,
          onChunk: (chunk) => {
            setStatus('streaming');
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantTempId
                  ? { ...msg, content: msg.content + chunk }
                  : msg,
              ),
            );
          },
          onDone: () => {
            setStatus('idle');
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantTempId ? { ...msg, isStreaming: false } : msg,
              ),
            );
          },
          onError: (streamError) => {
            streamFailure = streamError;
            setStatus('error');
            setError(streamError.message);
          },
        });

        if (streamFailure) {
          throw streamFailure;
        }

        setThreads((prev) =>
          prev.map((t) => (t.id === threadId ? { ...t, updatedAt: new Date() } : t)),
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : String(err);
        setStatus('error');
        setError(errorMessage);
        // Stop any assistant message stuck in loading/streaming state
        setMessages((prev) =>
          prev.map((msg) =>
            msg.isStreaming
              ? { ...msg, isStreaming: false, content: msg.content || `⚠ ${errorMessage}` }
              : msg,
          ),
        );
        throw err;
      }
    },
    [accessToken, activeThreadId, loadMessages, loadThreads, status],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setStatus('idle');
    setMessages((prev) => prev.map((msg) => ({ ...msg, isStreaming: false })));
  }, []);

  const userLabel = useMemo(() => userEmail.split('@')[0] || userEmail, [userEmail]);

  return (
    <div className="chat-page">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={handleSelectThread}
        onNewThread={handleNewThread}
        onDeleteThread={(threadId) => {
          void handleDeleteThread(threadId);
        }}
        onRenameThread={(threadId, title) => {
          void handleRenameThread(threadId, title);
        }}
        userLabel={userLabel}
        onSignOut={() => {
          void onSignOut();
        }}
        onOpenSheetAgent={onOpenSheetAgent}
        onOpenResearchAgent={onOpenResearchAgent}
        onOpenTicTacToe={onOpenTicTacToe}
      />

      <main className="chat-main">
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        <div className="chat-body">
          <MessageList messages={messages} />
        </div>

        <InputBar onSend={handleSend} onStop={stopStreaming} status={status} />
      </main>
    </div>
  );
}
