const colors: Record<string, string> = {
  pending: 'bg-slate-600 text-slate-200',
  planning: 'bg-amber-700 text-amber-100',
  in_progress: 'bg-amber-700 text-amber-100',
  executing: 'bg-blue-700 text-blue-100',
  completed: 'bg-green-700 text-green-100',
  failed: 'bg-red-700 text-red-100',
};

export function StatusBadge({ status }: { status: string }) {
  const cls = colors[status] || 'bg-slate-600 text-slate-200';
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
