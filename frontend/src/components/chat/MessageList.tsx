import { useEffect, useRef } from 'react';
import type { Components } from 'react-markdown';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
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
  comparisonTable?: ComparisonTableData;
  afterTable: string;
}

function formatMessageTime(value: Date): string {
  return value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const markdownComponents: Components = {
  table: ({ children }) => (
    <div className="sheet-table-scroll">
      <table>{children}</table>
    </div>
  ),
};

function parseMessageParts(content: string): MessageParts {
  const compRegex = /\[COMPARISON_TABLE\]([\s\S]*?)\[\/COMPARISON_TABLE\]/;
  const compMatch = content.match(compRegex);
  if (!compMatch) {
    return { beforeTable: content, afterTable: '' };
  }
  const beforeTable = content.substring(0, compMatch.index);
  const afterTable = content.substring(compMatch.index! + compMatch[0].length);
  try {
    const tableData: ComparisonTableData = JSON.parse(compMatch[1]);
    return { beforeTable, comparisonTable: tableData, afterTable };
  } catch {
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
  const messageParts = isUser ? { beforeTable: message.content, afterTable: '' } : parseMessageParts(message.content);

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
                <div className="message-assistant-summary">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{messageParts.beforeTable}</ReactMarkdown>
                </div>
              )}
              {message.intermediateSql && (
                <div className="sql-query-panel">
                  <div className="sql-query-title">SQL Query</div>
                  <SyntaxHighlighter
                    language="sql"
                    style={oneDark}
                    customStyle={{ margin: '8px 0 0', borderRadius: '10px' }}
                  >
                    {message.intermediateSql}
                  </SyntaxHighlighter>
                </div>
              )}
              {messageParts.comparisonTable && (
                <ComparisonTable
                  title={messageParts.comparisonTable.title}
                  leftHeader={messageParts.comparisonTable.leftHeader}
                  rightHeader={messageParts.comparisonTable.rightHeader}
                  rows={messageParts.comparisonTable.rows}
                />
              )}
              {messageParts.afterTable && (
                <div className="message-assistant-summary">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{messageParts.afterTable}</ReactMarkdown>
                </div>
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

