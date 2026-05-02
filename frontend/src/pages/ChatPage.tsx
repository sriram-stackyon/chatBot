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
  renameThread,
  streamChat,
} from '../lib/apiClient';
import { ChatStatus, Message, Thread } from '../types/chat';

interface ChatPageProps {
  accessToken: string;
  userEmail: string;
  onSignOut: () => Promise<void>;
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

function toMessageModel(item: {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}): Message {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    timestamp: new Date(item.created_at),
  };
}

export function ChatPage({ accessToken, userEmail, onSignOut }: ChatPageProps) {
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
      setMessages(data.map(toMessageModel));
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
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || status === 'loading' || status === 'streaming') return;

      try {
        setError(null);
        setStatus('loading');

        let threadId = activeThreadId;
        if (!threadId) {
          const created = await createThread(accessToken, trimmed.slice(0, 80));
          const mapped = toThreadModel(created);
          setThreads((prev) => [mapped, ...prev]);
          setActiveThreadId(mapped.id);
          threadId = mapped.id;
        }

        const userMessage: Message = {
          id: uuidv4(),
          role: 'user',
          content: trimmed,
          timestamp: new Date(),
        };

        const assistantTempId = uuidv4();
        const assistantTemp: Message = {
          id: assistantTempId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        };

        setMessages((prev) => [...prev, userMessage, assistantTemp]);

        abortRef.current = new AbortController();

        await streamChat({
          token: accessToken,
          threadId,
          message: trimmed,
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
            setStatus('error');
            setError(streamError.message);
          },
        });

        await loadThreads();
        await loadMessages(threadId);
      } catch (err) {
        setStatus('error');
        setError(err instanceof Error ? err.message : String(err));
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

        <InputBar onSend={(msg) => void handleSend(msg)} onStop={stopStreaming} status={status} />
      </main>
    </div>
  );
}
