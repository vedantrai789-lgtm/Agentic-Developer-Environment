import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getProject } from '../api/projects';
import { createTask, listTasks } from '../api/tasks';
import type { ProjectDetail as ProjectDetailType, Task } from '../api/types';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { StatusBadge } from '../components/StatusBadge';

export function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectDetailType | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    const load = async () => {
      try {
        const [proj, taskList] = await Promise.all([
          getProject(projectId),
          listTasks(projectId),
        ]);
        setProject(proj);
        setTasks(taskList);
      } catch {
        // handle error
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [projectId]);

  const handleCreateTask = async (description: string) => {
    if (!projectId) return;
    const task = await createTask(projectId, description);
    navigate(`/tasks/${task.id}`);
  };

  if (loading || !project) {
    return <p className="text-slate-400">Loading...</p>;
  }

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-xs text-slate-400 hover:text-white no-underline">
          &larr; Projects
        </Link>
        <h1 className="mt-2 text-2xl font-bold">{project.name}</h1>
        <p className="mt-1 font-mono text-sm text-slate-400">{project.path}</p>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <p className="text-xs text-slate-400">Tasks</p>
          <p className="text-2xl font-bold">{project.task_count}</p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <p className="text-xs text-slate-400">Embeddings</p>
          <p className="text-2xl font-bold">{project.embedding_count}</p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <p className="text-xs text-slate-400">Last Indexed</p>
          <p className="text-sm font-medium">
            {project.last_indexed_at
              ? new Date(project.last_indexed_at).toLocaleString()
              : 'Never'}
          </p>
        </div>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Tasks</h2>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-500"
        >
          New Task
        </button>
      </div>

      {tasks.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-8 text-center">
          <p className="text-slate-400">No tasks yet.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <Link
              key={task.id}
              to={`/tasks/${task.id}`}
              className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 no-underline transition hover:border-slate-500"
            >
              <div>
                <p className="text-sm text-white">{task.description}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {new Date(task.created_at).toLocaleString()}
                </p>
              </div>
              <StatusBadge status={task.status} />
            </Link>
          ))}
        </div>
      )}

      <CreateTaskModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreateTask}
      />
    </div>
  );
}
