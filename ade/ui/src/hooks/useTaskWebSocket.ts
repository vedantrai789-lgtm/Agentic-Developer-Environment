import { useEffect, useRef } from 'react';
import { wsUrl } from '../api/client';
import type { TaskEvent } from '../api/types';

export function useTaskWebSocket(
  taskId: string | undefined,
  onEvent: (event: TaskEvent) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!taskId) return;

    const url = wsUrl(`/tasks/${taskId}`);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const event: TaskEvent = JSON.parse(ev.data);
        if (event.event_type === 'ping') return;
        onEventRef.current(event);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId]);
}
