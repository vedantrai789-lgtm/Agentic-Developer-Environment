import type { AgentLog } from '../api/types';

export function LogsTable({ logs }: { logs: AgentLog[] }) {
  if (logs.length === 0) {
    return <p className="text-sm text-slate-500">No logs yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="border-b border-slate-700 text-slate-400">
          <tr>
            <th className="px-3 py-2">Timestamp</th>
            <th className="px-3 py-2">Agent</th>
            <th className="px-3 py-2">Action</th>
            <th className="px-3 py-2 text-right">In Tokens</th>
            <th className="px-3 py-2 text-right">Out Tokens</th>
            <th className="px-3 py-2 text-right">Latency</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-b border-slate-800 hover:bg-slate-800/50">
              <td className="px-3 py-2 font-mono text-slate-400">
                {new Date(log.timestamp).toLocaleTimeString()}
              </td>
              <td className="px-3 py-2">{log.agent_name}</td>
              <td className="px-3 py-2">{log.action}</td>
              <td className="px-3 py-2 text-right font-mono">{log.input_tokens}</td>
              <td className="px-3 py-2 text-right font-mono">{log.output_tokens}</td>
              <td className="px-3 py-2 text-right font-mono">{log.latency_ms.toFixed(0)}ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
