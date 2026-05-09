import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Message } from '../../types/chat';
import { MessageAttachments } from './MessageAttachments';
import { ComparisonTable } from './ComparisonTable';

interface Props {
  messages: Message[];
}

interface ComparisonTableData {
  title?: string;
  leftHeader: string;
  rightHeader: string;
  rows: Array<{
    aspect: string;
    left: string;
    right: string;
  }>;
}

interface MessageParts {
  beforeTable: string;
  table?: ComparisonTableData;
  afterTable: string;
}

function formatMessageTime(value: Date): string {
  return value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function parseMessageForTable(content: string): MessageParts {
  const tableRegex = /\[COMPARISON_TABLE\]([\s\S]*?)\[\/COMPARISON_TABLE\]/;
  const match = content.match(tableRegex);

  if (!match) {
    return { beforeTable: content, afterTable: '' };
  }

  const beforeTable = content.substring(0, match.index);
  const afterTable = content.substring(match.index! + match[0].length);

  try {
    const tableData: ComparisonTableData = JSON.parse(match[1]);
    return { beforeTable, table: tableData, afterTable };
  } catch {
    // If JSON parsing fails, treat as regular content
    return { beforeTable: content, afterTable: '' };
  }
}

export function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <p>Start a conversation by typing a message below.</p>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  const messageParts = isUser ? { beforeTable: message.content, afterTable: '' } : parseMessageForTable(message.content);

  return (
    <div className={`message-row ${isUser ? 'message-row-user' : 'message-row-assistant'}`}>
      <div className={`message-card ${isUser ? 'message-card-user' : 'message-card-assistant'}`}>
        <div className="message-meta">
          <span className={`message-role ${isUser ? 'message-role-user' : 'message-role-assistant'}`}>
            {isUser ? 'You' : 'Assistant'}
          </span>
          <span className="message-time">{formatMessageTime(message.timestamp)}</span>
        </div>
        <div className={`message-bubble ${isUser ? 'message-user' : 'message-assistant'}`}>
          {isUser ? (
            message.content
          ) : (
            <>
              {messageParts.beforeTable && (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{messageParts.beforeTable}</ReactMarkdown>
              )}
              {messageParts.table && (
                <ComparisonTable
                  title={messageParts.table.title}
                  leftHeader={messageParts.table.leftHeader}
                  rightHeader={messageParts.table.rightHeader}
                  rows={messageParts.table.rows}
                />
              )}
              {messageParts.afterTable && (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{messageParts.afterTable}</ReactMarkdown>
              )}
            </>
          )}
        </div>
        {message.attachments && message.attachments.length > 0 && (
          <MessageAttachments attachments={message.attachments} />
        )}
        {message.isStreaming && !message.content && <span className="cursor-blink">▋</span>}
        {message.isStreaming && message.content && <span className="cursor-blink"> ▋</span>}
      </div>
    </div>
  );
}
