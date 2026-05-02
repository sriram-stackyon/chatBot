import { KeyboardEvent, useCallback, useRef, useState } from 'react';
import { ChatStatus } from '../../types/chat';

interface Props {
  onSend: (message: string) => void;
  onStop: () => void;
  status: ChatStatus;
}

export function InputBar({ onSend, onStop, status }: Props) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isActive = status === 'loading' || status === 'streaming';

  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isActive) return;
    onSend(trimmed);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, isActive, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
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
          onClick={handleSend}
          disabled={!input.trim()}
          aria-label="Send message"
        >
          Send
        </button>
      )}
    </div>
  );
}
