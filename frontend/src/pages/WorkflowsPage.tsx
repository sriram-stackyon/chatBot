import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getWorkflowHistory,
  getWorkflowList,
  getWorkflowStats,
  runWorkflow,
  WorkflowDefinition,
  WorkflowExecution,
  WorkflowRunResult,
  WorkflowStats,
} from '../lib/workflowApi';

// ---------------------------------------------------------------------------
// Icons (inline SVG, no extra deps)
// ---------------------------------------------------------------------------

function IconPlay() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  );
}

function IconWorkflow() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="15" y="3" width="6" height="6" rx="1" />
      <rect x="9" y="15" width="6" height="6" rx="1" />
      <path d="M6 9v3a3 3 0 003 3h6a3 3 0 003-3V9" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconX() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconBack() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

interface ToastMsg {
  id: number;
  type: 'success' | 'error' | 'info';
  text: string;
}

function Toast({ toasts, onDismiss }: { toasts: ToastMsg[]; onDismiss: (id: number) => void }) {
  return (
    <div className="wf-toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`wf-toast wf-toast-${t.type}`}>
          <span>{t.text}</span>
          <button className="wf-toast-close" onClick={() => onDismiss(t.id)} aria-label="Dismiss">×</button>
        </div>
      ))}
    </div>
  );
}

function useToast() {
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const counterRef = useRef(0);

  const push = useCallback((type: ToastMsg['type'], text: string) => {
    const id = ++counterRef.current;
    setToasts((prev) => [...prev, { id, type, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, push, dismiss };
}

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------

function StatsBar({ stats, loading }: { stats: WorkflowStats | null; loading: boolean }) {
  const items = [
    { label: 'Total Runs', value: stats?.total_executions ?? 0 },
    { label: 'Successful', value: stats?.successful ?? 0 },
    { label: 'Failed', value: stats?.failed ?? 0 },
    { label: 'Success Rate', value: stats ? `${stats.success_rate}%` : '—' },
  ];

  return (
    <div className="wf-stats-bar">
      {items.map((item) => (
        <div key={item.label} className="wf-stat-card">
          {loading ? (
            <div className="wf-skeleton wf-skeleton-stat" />
          ) : (
            <span className="wf-stat-value">{item.value}</span>
          )}
          <span className="wf-stat-label">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workflow card
// ---------------------------------------------------------------------------

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: 'wf-pill-active',
    inactive: 'wf-pill-inactive',
  };
  return (
    <span className={`wf-pill ${map[status] ?? 'wf-pill-inactive'}`}>
      {status}
    </span>
  );
}

interface WorkflowCardProps {
  wf: WorkflowDefinition;
  running: boolean;
  onRun: () => void;
  onDetails: () => void;
}

function WorkflowCard({ wf, running, onRun, onDetails }: WorkflowCardProps) {
  return (
    <div className="wf-card">
      <div className="wf-card-header">
        <div className="wf-card-icon">
          <IconWorkflow />
        </div>
        <div className="wf-card-title-block">
          <h3 className="wf-card-name">{wf.name}</h3>
          <StatusPill status={wf.status} />
        </div>
      </div>

      <div className="wf-card-meta">
        <div className="wf-meta-row">
          <span className="wf-meta-label">Trigger</span>
          <span className="wf-meta-value">{wf.trigger_type}</span>
        </div>
        <div className="wf-meta-row">
          <span className="wf-meta-label">Executions</span>
          <span className="wf-meta-value">{wf.execution_count}</span>
        </div>
        <div className="wf-meta-row">
          <span className="wf-meta-label">Success Rate</span>
          <span className="wf-meta-value">{wf.success_rate}%</span>
        </div>
        <div className="wf-meta-row">
          <span className="wf-meta-label">Last Run</span>
          <span className="wf-meta-value">
            {wf.last_execution
              ? new Date(wf.last_execution).toLocaleString()
              : 'Never'}
          </span>
        </div>
      </div>

      <div className="wf-card-actions">
        <button
          className="wf-btn wf-btn-run"
          onClick={onRun}
          disabled={running}
          aria-label={`Run ${wf.name}`}
        >
          {running ? (
            <span className="wf-spinner" aria-hidden="true" />
          ) : (
            <IconPlay />
          )}
          {running ? 'Running…' : 'Run Now'}
        </button>
        <button className="wf-btn wf-btn-details" onClick={onDetails}>
          Details
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Execution log panel
// ---------------------------------------------------------------------------

function ExecutionLogs({
  executions,
  loading,
  lastResult,
}: {
  executions: WorkflowExecution[];
  loading: boolean;
  lastResult: WorkflowRunResult | null;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [executions.length]);

  return (
    <div className="wf-logs-panel">
      <div className="wf-logs-header">
        <span className="wf-logs-title">Execution Activity</span>
        {lastResult && (
          <span className={`wf-pill ${lastResult.success ? 'wf-pill-active' : 'wf-pill-error'}`}>
            {lastResult.success ? 'Last run succeeded' : 'Last run failed'}
          </span>
        )}
      </div>

      {lastResult && (
        <div className="wf-result-banner">
          <div className="wf-result-row">
            <span className="wf-result-label">Workflow</span>
            <span className="wf-result-value">{lastResult.workflow}</span>
          </div>
          <div className="wf-result-row">
            <span className="wf-result-label">Duration</span>
            <span className="wf-result-value">{lastResult.execution_time}</span>
          </div>
          <div className="wf-result-row">
            <span className="wf-result-label">Message</span>
            <span className="wf-result-value">{lastResult.message}</span>
          </div>
          {Object.keys(lastResult.data).length > 0 && (
            <details className="wf-result-data">
              <summary>Response payload</summary>
              <pre>{JSON.stringify(lastResult.data, null, 2)}</pre>
            </details>
          )}
        </div>
      )}

      <div className="wf-log-list">
        {loading && executions.length === 0 && (
          <>
            {[1, 2, 3].map((i) => (
              <div key={i} className="wf-skeleton wf-skeleton-log" />
            ))}
          </>
        )}
        {!loading && executions.length === 0 && (
          <p className="wf-logs-empty">No executions yet. Run a workflow to see logs here.</p>
        )}
        {executions.map((ex) => (
          <div key={ex.id} className={`wf-log-entry wf-log-${ex.status}`}>
            <span className="wf-log-icon">
              {ex.status === 'success' ? <IconCheck /> : ex.status === 'failed' ? <IconX /> : <span className="wf-spinner-xs" />}
            </span>
            <div className="wf-log-body">
              <span className="wf-log-name">{ex.workflow_name}</span>
              <span className="wf-log-time">{new Date(ex.triggered_at).toLocaleString()}</span>
            </div>
            <div className="wf-log-right">
              {ex.execution_time && (
                <span className="wf-log-duration">{ex.execution_time}</span>
              )}
              <span className={`wf-log-status wf-log-status-${ex.status}`}>{ex.status}</span>
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Details drawer
// ---------------------------------------------------------------------------

function DetailsDrawer({
  wf,
  onClose,
}: {
  wf: WorkflowDefinition;
  onClose: () => void;
}) {
  return (
    <div className="wf-drawer-overlay" onClick={onClose}>
      <aside className="wf-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="wf-drawer-header">
          <h2 className="wf-drawer-title">Workflow Details</h2>
          <button className="wf-drawer-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="wf-drawer-body">
          <section className="wf-drawer-section">
            <h3 className="wf-drawer-section-title">Metadata</h3>
            <div className="wf-drawer-row">
              <span>Name</span><span>{wf.name}</span>
            </div>
            <div className="wf-drawer-row">
              <span>Status</span><StatusPill status={wf.status} />
            </div>
            <div className="wf-drawer-row">
              <span>Trigger</span><span>{wf.trigger_type}</span>
            </div>
          </section>

          <section className="wf-drawer-section">
            <h3 className="wf-drawer-section-title">Endpoint</h3>
            <div className="wf-drawer-row">
              <span>Method</span><span className="wf-badge">POST</span>
            </div>
            <div className="wf-drawer-row">
              <span>Path</span>
              <code className="wf-drawer-code">{wf.webhook_path}</code>
            </div>
          </section>

          <section className="wf-drawer-section">
            <h3 className="wf-drawer-section-title">Request Payload</h3>
            <pre className="wf-drawer-pre">{JSON.stringify({ source: 'vue_dashboard', triggered_by: 'manual_user' }, null, 2)}</pre>
          </section>

          <section className="wf-drawer-section">
            <h3 className="wf-drawer-section-title">Statistics</h3>
            <div className="wf-drawer-row">
              <span>Total Runs</span><span>{wf.execution_count}</span>
            </div>
            <div className="wf-drawer-row">
              <span>Success Rate</span><span>{wf.success_rate}%</span>
            </div>
            <div className="wf-drawer-row">
              <span>Last Execution</span>
              <span>{wf.last_execution ? new Date(wf.last_execution).toLocaleString() : 'Never'}</span>
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

interface WorkflowsPageProps {
  accessToken: string;
  userEmail: string;
  onBack: () => void;
}

export function WorkflowsPage({ accessToken, onBack }: WorkflowsPageProps) {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<WorkflowRunResult | null>(null);
  const [drawerWf, setDrawerWf] = useState<WorkflowDefinition | null>(null);
  const [search, setSearch] = useState('');

  const { toasts, push: pushToast, dismiss } = useToast();

  const loadAll = useCallback(async () => {
    setLoadingData(true);
    try {
      const [wfList, hist, st] = await Promise.all([
        getWorkflowList(accessToken),
        getWorkflowHistory(accessToken),
        getWorkflowStats(accessToken),
      ]);
      setWorkflows(wfList);
      setExecutions(hist);
      setStats(st);
    } catch (err) {
      pushToast('error', err instanceof Error ? err.message : 'Failed to load workflow data');
    } finally {
      setLoadingData(false);
    }
  }, [accessToken, pushToast]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleRun = useCallback(
    async (wfId: string) => {
      if (runningId) return;
      setRunningId(wfId);
      try {
        const result = await runWorkflow(accessToken);
        setLastResult(result);
        pushToast('success', `Workflow executed in ${result.execution_time}`);
        // Refresh history and stats after execution
        const [hist, st, wfList] = await Promise.all([
          getWorkflowHistory(accessToken),
          getWorkflowStats(accessToken),
          getWorkflowList(accessToken),
        ]);
        setExecutions(hist);
        setStats(st);
        setWorkflows(wfList);
      } catch (err) {
        pushToast('error', err instanceof Error ? err.message : 'Workflow execution failed');
      } finally {
        setRunningId(null);
      }
    },
    [accessToken, pushToast, runningId],
  );

  const filteredWorkflows = search.trim()
    ? workflows.filter((w) => w.name.toLowerCase().includes(search.toLowerCase()))
    : workflows;

  return (
    <div className="wf-page">
      <Toast toasts={toasts} onDismiss={dismiss} />

      {/* Header */}
      <header className="wf-header">
        <div className="wf-header-left">
          <button className="wf-back-btn" onClick={onBack} aria-label="Back to chat">
            <IconBack /> Back
          </button>
          <div>
            <h1 className="wf-page-title">Workflows</h1>
            <p className="wf-page-subtitle">Manage and monitor your n8n automation workflows</p>
          </div>
        </div>
        <div className="wf-header-right">
          <input
            className="wf-search"
            type="search"
            placeholder="Search workflows…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search workflows"
          />
          <button className="wf-btn wf-btn-refresh" onClick={loadAll} disabled={loadingData} aria-label="Refresh">
            <IconRefresh />
          </button>
          <button
            className="wf-btn wf-btn-run-primary"
            onClick={() => workflows[0] && handleRun(workflows[0].id)}
            disabled={!!runningId || workflows.length === 0}
          >
            {runningId ? <span className="wf-spinner" /> : <IconPlay />}
            {runningId ? 'Running…' : 'Run Workflow'}
          </button>
        </div>
      </header>

      {/* Stats */}
      <StatsBar stats={stats} loading={loadingData} />

      {/* Body */}
      <div className="wf-body">
        {/* Workflow cards column */}
        <div className="wf-cards-col">
          {loadingData && filteredWorkflows.length === 0 ? (
            [1].map((i) => <div key={i} className="wf-skeleton wf-skeleton-card" />)
          ) : filteredWorkflows.length === 0 ? (
            <p className="wf-empty">No workflows found.</p>
          ) : (
            filteredWorkflows.map((wf) => (
              <WorkflowCard
                key={wf.id}
                wf={wf}
                running={runningId === wf.id}
                onRun={() => handleRun(wf.id)}
                onDetails={() => setDrawerWf(wf)}
              />
            ))
          )}
        </div>

        {/* Logs column */}
        <ExecutionLogs executions={executions} loading={loadingData} lastResult={lastResult} />
      </div>

      {/* Drawer */}
      {drawerWf && (
        <DetailsDrawer wf={drawerWf} onClose={() => setDrawerWf(null)} />
      )}
    </div>
  );
}
