import { apiFetch } from './client';
import type { AgentLog, Task, TaskDetail } from './types';

export function createTask(projectId: string, description: string): Promise<Task> {
  return apiFetch<Task>(`/projects/${projectId}/tasks`, {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}

export function listTasks(projectId: string, status?: string): Promise<Task[]> {
  const params = status ? `?status=${status}` : '';
  return apiFetch<Task[]>(`/projects/${projectId}/tasks${params}`);
}

export function getTask(taskId: string): Promise<TaskDetail> {
  return apiFetch<TaskDetail>(`/tasks/${taskId}`);
}

export function getTaskLogs(taskId: string, agentName?: string): Promise<AgentLog[]> {
  const params = agentName ? `?agent_name=${agentName}` : '';
  return apiFetch<AgentLog[]>(`/tasks/${taskId}/logs${params}`);
}
