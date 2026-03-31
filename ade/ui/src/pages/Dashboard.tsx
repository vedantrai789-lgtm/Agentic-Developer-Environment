import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CreateProjectModal } from '../components/CreateProjectModal';
import { listProjects, createProject } from '../api/projects';
import type { Project } from '../api/types';

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await listProjects();
      setProjects(data);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreate = async (name: string, path: string) => {
    await createProject(name, path);
    await fetchProjects();
  };

  if (loading) {
    return <p className="text-slate-400">Loading projects...</p>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projects</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-500"
        >
          New Project
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

      {projects.length === 0 ? (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-8 text-center">
          <p className="text-slate-400">No projects yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="rounded-lg border border-slate-700 bg-slate-800 p-4 no-underline transition hover:border-slate-500"
            >
              <h3 className="font-semibold text-white">{project.name}</h3>
              <p className="mt-1 truncate text-xs text-slate-400 font-mono">{project.path}</p>
              <p className="mt-2 text-xs text-slate-500">
                {project.last_indexed_at
                  ? `Indexed ${new Date(project.last_indexed_at).toLocaleDateString()}`
                  : 'Not indexed'}
              </p>
            </Link>
          ))}
        </div>
      )}

      <CreateProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
}
