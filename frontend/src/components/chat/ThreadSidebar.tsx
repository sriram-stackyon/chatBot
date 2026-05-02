import { Thread } from '../../types/chat';
import { KeyboardEvent, useState } from 'react';

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-plus">
      <path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-trash">
      <path
        d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6v9m4-9v9M7 7l1 13a2 2 0 002 2h4a2 2 0 002-2l1-13"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="icon-edit">
      <path
        d="M4 16.5V20h3.5L18 9.5 14.5 6 4 16.5zm12.8-11.3 1 1a1.5 1.5 0 010 2.1l-1 1L14 6.5l1-1a1.5 1.5 0 012.1 0z"
        fill="currentColor"
      />
    </svg>
  );
}

interface Props {
  threads: Thread[];
  activeThreadId: string | null;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  onDeleteThread: (id: string) => void;
  onRenameThread: (id: string, title: string) => void;
  userLabel: string;
  onSignOut: () => void;
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onRenameThread,
  userLabel,
  onSignOut,
}: Props) {
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState('');

  function beginRename(threadId: string, currentTitle: string): void {
    setEditingThreadId(threadId);
    setDraftTitle(currentTitle);
  }

  function cancelRename(): void {
    setEditingThreadId(null);
    setDraftTitle('');
  }

  function commitRename(threadId: string): void {
    const nextTitle = draftTitle.trim();
    if (!nextTitle) {
      cancelRename();
      return;
    }
    onRenameThread(threadId, nextTitle);
    cancelRename();
  }

  function onDraftKeyDown(event: KeyboardEvent<HTMLInputElement>, threadId: string): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      commitRename(threadId);
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelRename();
    }
  }

  return (
    <aside className="thread-sidebar">
      <div className="sidebar-body">
        <button className="btn-new-chat" onClick={onNewThread} aria-label="New conversation">
          <span className="new-chat-plus"><PlusIcon /></span>
          <span>New Chat</span>
        </button>

        <nav className="thread-list" aria-label="Conversation threads">
          {threads.length === 0 && (
            <p className="sidebar-empty">No conversations yet.</p>
          )}
          {threads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            const isEditing = thread.id === editingThreadId;
            return (
              <div
                key={thread.id}
                className={`thread-item ${isActive ? 'thread-item-active' : ''}`}
              >
                <button
                  className="thread-main"
                  onClick={() => onSelectThread(thread.id)}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {isEditing ? (
                    <input
                      className="thread-edit-input"
                      value={draftTitle}
                      onChange={(event) => setDraftTitle(event.target.value)}
                      onKeyDown={(event) => onDraftKeyDown(event, thread.id)}
                      onBlur={() => commitRename(thread.id)}
                      autoFocus
                      maxLength={120}
                      aria-label="Thread title"
                    />
                  ) : (
                    <span className="thread-title">{thread.title}</span>
                  )}
                </button>

                <div className="thread-actions">
                  <button
                    className="thread-icon-btn"
                    type="button"
                    onClick={() => beginRename(thread.id, thread.title)}
                    aria-label={`Rename ${thread.title}`}
                  >
                    <EditIcon />
                  </button>
                  <button
                    className="thread-icon-btn"
                    type="button"
                    onClick={() => onDeleteThread(thread.id)}
                    aria-label={`Delete ${thread.title}`}
                  >
                    <TrashIcon />
                  </button>
                </div>
              </div>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        <span className="sidebar-user">{userLabel}</span>
        <button className="btn-signout" type="button" onClick={onSignOut}>
          Sign out
        </button>
      </div>
    </aside>
  );
}

export default ThreadSidebar;
