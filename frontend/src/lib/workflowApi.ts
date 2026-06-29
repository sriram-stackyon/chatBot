/**
 * Workflow API service — all n8n workflow-related network calls.
 * The webhook URL is NEVER exposed here; calls go to FastAPI which
 * proxies to n8n.
 */

const env = import.meta.env as Record<string, string | undefined>;
const API_BASE = (env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WorkflowRunResult {
  success: boolean;
  message: string;
  execution_time: string;
  workflow: string;
  data: Record<string, unknown>;
}

export interface WorkflowExecution {
  id: string;
  workflow_name: string;
  status: 'success' | 'failed' | 'running';
  triggered_at: string;
  execution_time: string | null;
  triggered_by: string;
}

export interface WorkflowStats {
  total_executions: number;
  successful: number;
  failed: number;
  success_rate: number;
  last_run: string | null;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  status: string;
  trigger_type: string;
  webhook_path: string;
  last_execution: string | null;
  execution_count: number;
  success_rate: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function runWorkflow(token: string): Promise<WorkflowRunResult> {
  const res = await fetch(`${API_BASE}/api/workflows/run-news-digest`, {
    method: 'POST',
    headers: authHeaders(token),
  });
  return handleResponse<WorkflowRunResult>(res);
}

export async function getWorkflowHistory(token: string): Promise<WorkflowExecution[]> {
  const res = await fetch(`${API_BASE}/api/workflows/history`, {
    headers: authHeaders(token),
  });
  const body = await handleResponse<{ executions: WorkflowExecution[] }>(res);
  return body.executions;
}

export async function getWorkflowStats(token: string): Promise<WorkflowStats> {
  const res = await fetch(`${API_BASE}/api/workflows/stats`, {
    headers: authHeaders(token),
  });
  return handleResponse<WorkflowStats>(res);
}

export async function getWorkflowList(token: string): Promise<WorkflowDefinition[]> {
  const res = await fetch(`${API_BASE}/api/workflows/list`, {
    headers: authHeaders(token),
  });
  const body = await handleResponse<{ workflows: WorkflowDefinition[] }>(res);
  return body.workflows;
}
