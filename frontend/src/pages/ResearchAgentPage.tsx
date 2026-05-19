import { useCallback, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { streamResearch } from '../lib/api';
import { ArxivPaper } from '../types/chat';

interface ResearchAgentPageProps {
  accessToken: string;
  userEmail: string;
  onBack: () => void;
}

interface ConvMessage {
  role: 'user' | 'assistant';
  content: string;
}

const QUICK_QUERIES = [
  'Latest research on AI agents',
  'Recent RAG improvements and techniques',
  'Multimodal LLM research trends',
  'Autonomous AI and self-improving systems',
  'Vector database and embedding innovations',
  'LLM memory and long-context research',
  'Latest Gemini and GPT-4 research',
  'Research trends in AI safety and alignment',
];

function genId() {
  return Math.random().toString(36).slice(2);
}

export function ResearchAgentPage({ accessToken, userEmail, onBack }: ResearchAgentPageProps) {
  const [query, setQuery] = useState('');
  const [researching, setResearching] = useState(false);
  const [statusMessages, setStatusMessages] = useState<string[]>([]);
  const [papers, setPapers] = useState<ArxivPaper[]>([]);
  const [digest, setDigest] = useState('');
  const [digestDone, setDigestDone] = useState(false);
  const [error, setError] = useState('');
  const [conversationHistory, setConversationHistory] = useState<ConvMessage[]>([]);
  const [followUp, setFollowUp] = useState('');

  const abortRef = useRef<AbortController | null>(null);
  const digestRef = useRef<HTMLDivElement>(null);
  const statusEndRef = useRef<HTMLDivElement>(null);

  const startResearch = useCallback(
    (q: string) => {
      const trimmed = q.trim();
      if (!trimmed || researching) return;

      // Reset result state
      setError('');
      setStatusMessages([]);
      setPapers([]);
      setDigest('');
      setDigestDone(false);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setResearching(true);

      let accumulated = '';

      streamResearch({
        token: accessToken,
        query: trimmed,
        maxPapers: 12,
        conversationHistory: conversationHistory.map((m) => ({
          role: m.role,
          content: m.content,
        })),
        onStatus: (msg) => {
          setStatusMessages((prev) => [...prev, msg]);
          setTimeout(() => statusEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
        },
        onPapers: (p) => setPapers(p),
        onChunk: (text) => {
          accumulated += text;
          setDigest(accumulated);
          setTimeout(() => digestRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
        },
        onDone: () => {
          setResearching(false);
          setDigestDone(true);
          if (accumulated) {
            setConversationHistory((prev) => [
              ...prev,
              { role: 'user', content: trimmed },
              { role: 'assistant', content: accumulated },
            ]);
          }
        },
        onError: (err) => {
          setError(err.message);
          setResearching(false);
        },
        signal: controller.signal,
      });
    },
    [accessToken, conversationHistory, researching],
  );

  const handleStop = () => {
    abortRef.current?.abort();
    setResearching(false);
    setDigestDone(Boolean(digest));
  };

  const handleFollowUp = () => {
    const q = followUp.trim();
    if (!q) return;
    setFollowUp('');
    startResearch(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>, action: () => void) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      action();
    }
  };

  return (
    <div className="ra-page">
      {/* ── Top bar ── */}
      <header className="ra-topbar">
        <button className="ra-back-btn" onClick={onBack}>
          ← Chat
        </button>
        <div className="ra-topbar-center">
          <span className="ra-topbar-icon">🔬</span>
          <span className="ra-topbar-title">Research Digest Agent</span>
        </div>
        <span className="ra-topbar-user">{userEmail}</span>
      </header>

      <div className="ra-body">
        {/* ── Query Section ── */}
        <section className="ra-query-section">
          <div className="ra-query-header">
            <h2 className="ra-query-title">Explore arXiv Research</h2>
            <p className="ra-query-subtitle">
              Enter any research topic — the agent autonomously searches arXiv, evaluates papers,
              and streams a structured digest in real time.
            </p>
          </div>

          <div className="ra-chips">
            {QUICK_QUERIES.map((q) => (
              <button
                key={q}
                className="ra-chip"
                onClick={() => startResearch(q)}
                disabled={researching}
              >
                {q}
              </button>
            ))}
          </div>

          <div className="ra-input-row">
            <textarea
              className="ra-input"
              placeholder="e.g. Latest advances in transformer attention mechanisms..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => handleKeyDown(e, () => startResearch(query))}
              disabled={researching}
              rows={2}
            />
            <div className="ra-input-actions">
              {researching ? (
                <button className="ra-stop-btn" onClick={handleStop}>
                  ■ Stop
                </button>
              ) : (
                <button
                  className="ra-research-btn"
                  onClick={() => startResearch(query)}
                  disabled={!query.trim()}
                >
                  Research
                </button>
              )}
            </div>
          </div>
        </section>

        {/* ── Error ── */}
        {error && <div className="ra-error">⚠ {error}</div>}

        {/* ── Status Progress ── */}
        {statusMessages.length > 0 && (
          <section className="ra-status-section">
            <div className="ra-status-header">Research Progress</div>
            <div className="ra-status-list">
              {statusMessages.map((msg, i) => (
                <div
                  key={`${genId()}-${i}`}
                  className={`ra-status-item ${
                    i === statusMessages.length - 1 && researching
                      ? 'ra-status-active'
                      : 'ra-status-done'
                  }`}
                >
                  <span className="ra-status-dot" />
                  <span>{msg}</span>
                </div>
              ))}
              <div ref={statusEndRef} />
            </div>
          </section>
        )}

        {/* ── Papers Grid ── */}
        {papers.length > 0 && (
          <section className="ra-papers-section">
            <div className="ra-section-header">
              <span className="ra-section-title">Papers Found</span>
              <span className="ra-papers-badge">{papers.length} papers</span>
            </div>
            <div className="ra-papers-grid">
              {papers.map((paper) => (
                <article key={paper.arxiv_id} className="ra-paper-card">
                  <h3 className="ra-paper-title">
                    <a href={paper.arxiv_url} target="_blank" rel="noopener noreferrer">
                      {paper.title}
                    </a>
                  </h3>
                  <div className="ra-paper-meta">
                    <span className="ra-paper-authors">
                      {paper.authors.slice(0, 3).join(', ')}
                      {paper.authors.length > 3 ? ' et al.' : ''}
                    </span>
                    <span className="ra-paper-date">{paper.published}</span>
                  </div>
                  <p className="ra-paper-abstract">
                    {paper.summary.length > 220
                      ? `${paper.summary.slice(0, 220)}…`
                      : paper.summary}
                  </p>
                  <div className="ra-paper-links">
                    <a
                      className="ra-link-arxiv"
                      href={paper.arxiv_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      arXiv ↗
                    </a>
                    <a
                      className="ra-link-pdf"
                      href={paper.pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      PDF ↓
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {/* ── Research Digest (streaming) ── */}
        {digest && (
          <section className="ra-digest-section">
            <div className="ra-section-header">
              <span className="ra-section-title">Research Digest</span>
              {!digestDone && (
                <span className="ra-generating">
                  <span className="ra-generating-dot" />
                  Generating…
                </span>
              )}
            </div>
            <div className="ra-digest-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{digest}</ReactMarkdown>
            </div>
            <div ref={digestRef} />
          </section>
        )}

        {/* ── Follow-up Section ── */}
        {digestDone && (
          <section className="ra-followup-section">
            <div className="ra-followup-label">🔄 Follow-up Research</div>
            <p className="ra-followup-hint">
              Ask a follow-up question or explore a related angle — conversation context is
              preserved.
            </p>
            <div className="ra-input-row">
              <textarea
                className="ra-input"
                placeholder="e.g. Compare the top papers on attention efficiency in more detail..."
                value={followUp}
                onChange={(e) => setFollowUp(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, handleFollowUp)}
                rows={2}
              />
              <div className="ra-input-actions">
                <button
                  className="ra-research-btn"
                  onClick={handleFollowUp}
                  disabled={!followUp.trim() || researching}
                >
                  Research
                </button>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
