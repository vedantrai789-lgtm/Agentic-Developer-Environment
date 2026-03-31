import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getTask, getTaskLogs } from '../api/tasks';
import type { AgentLog, PlanStep, TaskDetail as TaskDetailType } from '../api/types';
import { DiffViewer } from '../components/DiffViewer';
import { LogsTable } from '../components/LogsTable';
import { StatusBadge } from '../components/StatusBadge';
import { useTaskWebSocket } from '../hooks/useTaskWebSocket';

export function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const [task, setTask] = useState<TaskDetailType | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [showLogs, setShowLogs] = useState(false);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const fetchTask = useCallback(async () => {
    if (!taskId) return;
    try {
      const data = await getTask(taskId);
      setTask(data);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    fetchTask();
  }, [fetchTask]);

  // Real-time updates via WebSocket
  useTaskWebSocket(taskId, () => {
    fetchTask();
  });

  const loadLogs = async () => {
    if (!taskId) return;
    setShowLogs(true);
    try {
      const data = await getTaskLogs(taskId);
      setLogs(data);
    } catch {
      // handle error
    }
  };

  if (loading || !task) {
    return <p className="text-slate-400">Loading...</p>;
  }

  const isActive = task.status === 'pending' || task.status === 'planning' || task.status === 'executing';

  return (
    <div>
      <div className="mb-6">
        <Link
          to={`/projects/${task.project_id}`}
          className="text-xs text-slate-400 hover:text-white no-underline"
        >
          &larr; Project
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-bold">Task</h1>
          <StatusBadge status={task.status} />
          {isActive && (
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-400" />
          )}
        </div>
        <p className="mt-2 text-sm text-slate-300">{task.description}</p>
        <p className="mt-1 text-xs text-slate-500">
          Created {new Date(task.created_at).toLocaleString()}
          {task.completed_at && ` · Completed ${new Date(task.completed_at).toLocaleString()}`}
        </p>
      </div>

      {/* Plan Steps Timeline */}
      <h2 className="mb-3 text-lg font-semibold">Plan Steps</h2>
      {task.plan_steps.length === 0 ? (
        <p className="text-sm text-slate-500">
          {isActive ? 'Waiting for plan...' : 'No plan steps.'}
        </p>
      ) : (
        <div className="space-y-3">
          {task.plan_steps.map((step) => (
            <StepCard
              key={step.id}
              step={step}
              expanded={expandedStep === step.id}
              onToggle={() =>
                setExpandedStep(expandedStep === step.id ? null : step.id)
              }
            />
          ))}
        </div>
      )}

      {/* Logs Section */}
      <div className="mt-8">
        {!showLogs ? (
          <button
            onClick={loadLogs}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            Show Agent Logs
          </button>
        ) : (
          <>
            <h2 className="mb-3 text-lg font-semibold">Agent Logs</h2>
            <LogsTable logs={logs} />
          </>
        )}
      </div>
    </div>
  );
}

function StepCard({
  step,
  expanded,
  onToggle,
}: {
  step: PlanStep;
  expanded: boolean;
  onToggle: () => void;
}) {
  const targetFiles = Array.isArray(step.target_files)
    ? step.target_files
    : [];

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-700 text-xs font-medium">
            {step.step_number}
          </span>
          <span className="text-sm">{step.description}</span>
        </div>
        <StatusBadge status={step.status} />
      </button>

      {expanded && (
        <div className="border-t border-slate-700 px-4 py-3 space-y-4">
          {/* Target Files */}
          {targetFiles.length > 0 && (
            <div>
              <p className="mb-1 text-xs text-slate-400">Target Files</p>
              <div className="flex flex-wrap gap-1">
                {targetFiles.map((f, i) => (
                  <span
                    key={i}
                    className="rounded bg-slate-700 px-2 py-0.5 text-xs font-mono text-slate-300"
                  >
                    {String(f)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Code Changes */}
          {step.code_changes.length > 0 && (
            <div>
              <p className="mb-2 text-xs text-slate-400">Code Changes</p>
              <div className="space-y-2">
                {step.code_changes.map((change) => (
                  <DiffViewer
                    key={change.id}
                    filePath={change.file_path}
                    changeType={change.change_type}
                    content={change.diff}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Execution Results */}
          {step.execution_results.length > 0 && (
            <div>
              <p className="mb-2 text-xs text-slate-400">Execution Results</p>
              {step.execution_results.map((result) => (
                <div
                  key={result.id}
                  className="rounded border border-slate-700 bg-slate-950 p-3"
                >
                  <div className="mb-2 flex items-center gap-3 text-xs">
                    <code className="text-slate-300">{result.command}</code>
                    <span
                      className={
                        result.exit_code === 0 ? 'text-green-400' : 'text-red-400'
                      }
                    >
                      exit {result.exit_code}
                    </span>
                    <span className="text-slate-500">{result.duration_ms}ms</span>
                  </div>
                  {result.stdout && (
                    <pre className="overflow-x-auto text-xs text-slate-400">
                      {result.stdout}
                    </pre>
                  )}
                  {result.stderr && (
                    <pre className="overflow-x-auto text-xs text-red-400">
                      {result.stderr}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}

          {step.code_changes.length === 0 && step.execution_results.length === 0 && (
            <p className="text-xs text-slate-500">No details yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
