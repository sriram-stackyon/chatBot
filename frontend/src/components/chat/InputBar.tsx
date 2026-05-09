import { KeyboardEvent, useCallback, useRef, useState } from 'react';

import { ChatStatus } from '../../types/chat';
import { AttachmentButton } from './AttachmentButton';
import { AttachmentPreview } from './AttachmentPreview';

interface Props {
  onSend: (message: string, files: File[]) => Promise<void> | void;
  onStop: () => void;
  status: ChatStatus;
}

export function InputBar({ onSend, onStop, status }: Props) {
  const [input, setInput] = useState('');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isActive = status === 'loading' || status === 'streaming';

  const appendFiles = useCallback((files: File[]) => {
    setPendingFiles((prev) => {
      const seen = new Set(prev.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const next = [...prev];
      for (const file of files) {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!seen.has(key)) {
          seen.add(key);
          next.push(file);
        }
      }
      return next;
    });
  }, []);

  const removeFile = useCallback((index: number) => {
    setPendingFiles((prev) => prev.filter((_, fileIndex) => fileIndex !== index));
  }, []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isActive) return;
    await onSend(trimmed, pendingFiles);
    setInput('');
    setPendingFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, isActive, onSend, pendingFiles]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void handleSend();
      }
    },
    [handleSend],
  );

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  return (
    <div className="input-bar">
      <AttachmentPreview
        files={pendingFiles}
        disabled={isActive}
        onFilesAdded={appendFiles}
        onRemove={removeFile}
      />
      <div className="input-row">
        <AttachmentButton disabled={isActive} onFilesSelected={appendFiles} />
        <textarea
          ref={textareaRef}
          className="input-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={autoResize}
          placeholder="Message... (Enter to send, Shift+Enter for new line)"
          rows={1}
          aria-label="Chat input"
        />
        {isActive ? (
          <button className="btn btn-stop" onClick={onStop} aria-label="Stop generation">
            ■ Stop
          </button>
        ) : (
          <button
            className="btn btn-send"
            onClick={() => {
              void handleSend();
            }}
            disabled={!input.trim()}
            aria-label="Send message"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
