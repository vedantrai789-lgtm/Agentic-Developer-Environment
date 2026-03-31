import { useState } from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, path: string) => Promise<void>;
}

export function CreateProjectModal({ open, onClose, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onSubmit(name, path);
      setName('');
      setPath('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-md rounded-lg bg-slate-800 p-6">
        <h2 className="mb-4 text-lg font-semibold">New Project</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Project Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="my-project"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Path</label>
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              required
              className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-white outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="/home/user/my-project"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
