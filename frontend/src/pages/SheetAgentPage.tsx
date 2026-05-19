import { useCallback, useRef, useState } from 'react';
import { previewSheet, querySheetChat, uploadSheetFile } from '../lib/api';
import { SheetPreviewResponse } from '../types/chat';

interface SheetAgentPageProps {
  accessToken: string;
  userEmail: string;
  onBack: () => void;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const QUICK_CHIPS = [
  'Generate summary of this sheet',
  'What trends do you see?',
  'Show top 5 rows by the most important numeric column',
  'Count active records',
  'How many rows are there?',
];

function genId() {
  return Math.random().toString(36).slice(2);
}

export function SheetAgentPage({ accessToken, userEmail, onBack }: SheetAgentPageProps) {
  // Source state
  const [sourceType, setSourceType] = useState<string>('');
  const [sourceValue, setSourceValue] = useState<string>('');
  const [gsheetUrl, setGsheetUrl] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Preview state
  const [preview, setPreview] = useState<SheetPreviewResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState('');

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [chatError, setChatError] = useState('');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const scrollChatToBottom = () => {
    setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  // ── File Upload ────────────────────────────────────────────────
  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setPreviewError('');
      setPreview(null);
      setMessages([]);
      setLoadingPreview(true);
      try {
        const uploaded = await uploadSheetFile(accessToken, file);
        setSourceType(uploaded.source_type);
        setSourceValue(uploaded.file_path);
        setUploadedFileName(uploaded.original_filename);
        setGsheetUrl('');

        const prev = await previewSheet(accessToken, uploaded.source_type, uploaded.file_path);
        setPreview(prev);
      } catch (err) {
        setPreviewError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoadingPreview(false);
      }
    },
    [accessToken],
  );

  // ── Google Sheet Import ────────────────────────────────────────
  const handleImportGsheet = useCallback(async () => {
    const url = gsheetUrl.trim();
    if (!url) return;
    setPreviewError('');
    setPreview(null);
    setMessages([]);
    setLoadingPreview(true);
    setUploadedFileName('');
    try {
      const prev = await previewSheet(accessToken, 'gsheet', url);
      setPreview(prev);
      setSourceType('gsheet');
      setSourceValue(url);
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingPreview(false);
    }
  }, [accessToken, gsheetUrl]);

  // ── Ask ────────────────────────────────────────────────────────
  const handleAsk = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed || !sourceType || !sourceValue || asking) return;
      setChatError('');
      setAsking(true);
      const userMsg: ChatMessage = { id: genId(), role: 'user', content: trimmed };
      const assistantMsg: ChatMessage = { id: genId(), role: 'assistant', content: '' };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setQuestion('');
      scrollChatToBottom();

      try {
        const res = await querySheetChat(accessToken, trimmed, sourceType, sourceValue);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsg.id ? { ...m, content: res.content } : m)),
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setChatError(msg);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantMsg.id ? { ...m, content: `⚠ ${msg}` } : m)),
        );
      } finally {
        setAsking(false);
        scrollChatToBottom();
      }
    },
    [accessToken, sourceType, sourceValue, asking],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleAsk(question);
    }
  };

  const hasSource = Boolean(sourceType && sourceValue);

  return (
    <div className="sa-page">
      {/* ── Top bar ── */}
      <header className="sa-topbar">
        <button className="sa-back-btn" onClick={onBack}>
          ← Chat
        </button>
        <span className="sa-topbar-title">Sheet Agent</span>
        <span className="sa-topbar-user">{userEmail}</span>
      </header>

      <div className="sa-body">
        {/* ── Left panel ── */}
        <aside className="sa-left">
          {/* Load section */}
          <div className="sa-card">
            <div className="sa-card-title">Load Spreadsheet</div>
            <p className="sa-card-subtitle">
              Upload CSV/XLSX files or paste a Google Sheets URL shared with your service account.
            </p>

            {/* File upload */}
            <div className="sa-upload-row">
              <span className="sa-upload-label">Upload CSV or XLSX</span>
              <div className="sa-upload-controls">
                <button className="sa-choose-btn" onClick={() => fileInputRef.current?.click()}>
                  Choose File
                </button>
                <span className="sa-filename">
                  {uploadedFileName || 'No file chosen'}
                </span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
            </div>

            {/* Google Sheet URL */}
            <div className="sa-gsheet-row">
              <input
                className="sa-url-input"
                type="text"
                placeholder="https://docs.google.com/spreadsheets/d/…"
                value={gsheetUrl}
                onChange={(e) => setGsheetUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void handleImportGsheet()}
              />
              <button
                className="sa-import-btn"
                onClick={() => void handleImportGsheet()}
                disabled={!gsheetUrl.trim() || loadingPreview}
              >
                {loadingPreview && !uploadedFileName ? 'Loading…' : 'Import Google Sheet'}
              </button>
            </div>

            {previewError && <p className="sa-error">{previewError}</p>}
            {loadingPreview && <p className="sa-loading">Loading spreadsheet…</p>}
          </div>

          {/* Preview section */}
          {preview && (
            <div className="sa-card sa-preview-card">
              <div className="sa-preview-header">
                <div>
                  <div className="sa-preview-name">{preview.source_name}</div>
                  <div className="sa-preview-meta">
                    {preview.columns.length} columns
                  </div>
                </div>
                <span className="sa-preview-rows-badge">Total rows: {preview.row_count}</span>
              </div>

              <div className="sa-table-scroll">
                <table className="sa-table">
                  <thead>
                    <tr>
                      {preview.columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview_rows.map((row, i) => (
                      <tr key={i}>
                        {preview.columns.map((col) => (
                          <td key={col}>{row[col] != null ? String(row[col]) : ''}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </aside>

        {/* ── Right panel ── */}
        <section className="sa-right">
          <div className="sa-ask-header">
            <span className="sa-ask-title">Ask About This Sheet</span>
            {hasSource && (
              <span className="sa-ask-subtitle">Conversational follow-up supported</span>
            )}
          </div>

          {/* Quick chips */}
          {hasSource && (
            <div className="sa-chips">
              {QUICK_CHIPS.map((chip) => (
                <button
                  key={chip}
                  className="sa-chip"
                  onClick={() => void handleAsk(chip)}
                  disabled={asking}
                >
                  {chip}
                </button>
              ))}
            </div>
          )}

          {/* Messages */}
          <div className="sa-messages">
            {!hasSource && (
              <div className="sa-no-source">
                Load a spreadsheet on the left to start querying.
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`sa-msg ${msg.role === 'user' ? 'sa-msg-user' : 'sa-msg-assistant'}`}
              >
                <div className="sa-msg-label">
                  {msg.role === 'user' ? userEmail.split('@')[0] : 'Assistant'}
                </div>
                <div className="sa-msg-bubble">
                  {msg.role === 'assistant' && !msg.content && asking ? (
                    <span className="sa-typing">▋</span>
                  ) : (
                    <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                  )}
                </div>
              </div>
            ))}
            {chatError && <p className="sa-error">{chatError}</p>}
            <div ref={chatBottomRef} />
          </div>

          {/* Input */}
          <div className="sa-input-row">
            <textarea
              className="sa-input"
              rows={2}
              placeholder={
                hasSource ? 'Ask a spreadsheet question…' : 'Load a spreadsheet first'
              }
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!hasSource || asking}
            />
            <button
              className="sa-ask-btn"
              onClick={() => void handleAsk(question)}
              disabled={!hasSource || !question.trim() || asking}
            >
              {asking ? '…' : 'Ask'}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
