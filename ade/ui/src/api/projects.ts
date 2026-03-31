import { apiFetch } from './client';
import type { Project, ProjectDetail } from './types';

export function listProjects(): Promise<Project[]> {
  return apiFetch<Project[]>('/projects/');
}

export function getProject(id: string): Promise<ProjectDetail> {
  return apiFetch<ProjectDetail>(`/projects/${id}`);
}

export function createProject(name: string, path: string): Promise<Project> {
  return apiFetch<Project>('/projects/', {
    method: 'POST',
    body: JSON.stringify({ name, path }),
  });
}
