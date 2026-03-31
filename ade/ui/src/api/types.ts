export interface Project {
  id: string;
  name: string;
  path: string;
  created_at: string;
  last_indexed_at: string | null;
}

export interface ProjectDetail extends Project {
  task_count: number;
  embedding_count: number;
}

export interface Task {
  id: string;
  project_id: string;
  description: string;
  status: 'pending' | 'planning' | 'executing' | 'completed' | 'failed';
  created_at: string;
  completed_at: string | null;
}

export interface CodeChange {
  id: string;
  file_path: string;
  change_type: 'create' | 'modify' | 'delete';
  diff: string | null;
}

export interface ExecutionResult {
  id: string;
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
}

export interface PlanStep {
  id: string;
  step_number: number;
  description: string;
  target_files: string[] | Record<string, unknown> | null;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  code_changes: CodeChange[];
  execution_results: ExecutionResult[];
}

export interface TaskDetail extends Task {
  plan_steps: PlanStep[];
}

export interface AgentLog {
  id: string;
  agent_name: string;
  action: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  timestamp: string;
  step_id: string | null;
}

export interface TaskEvent {
  task_id: string;
  event_type: 'status_change' | 'task_completed' | 'task_failed' | 'ping';
  data: Record<string, unknown>;
  timestamp: string;
}

export interface HealthResponse {
  status: string;
  database: boolean;
  redis: boolean;
}
