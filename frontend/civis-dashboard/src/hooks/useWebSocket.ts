import { useEffect, useRef, useState, useCallback } from 'react';
import { PipelineEventMessage } from '../types';

export type ConnectionState = 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED' | 'RECONNECTING';

interface UseWebSocketOptions {
  url: string;
  maxBuffer?: number;
  autoReconnect?: boolean;
  reconnectIntervalMs?: number;
  maxReconnectIntervalMs?: number;
}

export function useWebSocket({
  url,
  maxBuffer = 100,
  autoReconnect = true,
  reconnectIntervalMs = 1000,
  maxReconnectIntervalMs = 10000,
}: UseWebSocketOptions) {
  const [events, setEvents] = useState<PipelineEventMessage[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('CONNECTING');
  const [latestEvent, setLatestEvent] = useState<PipelineEventMessage | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    try {
      setConnectionState(reconnectAttemptRef.current > 0 ? 'RECONNECTING' : 'CONNECTING');
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setConnectionState('OPEN');
        reconnectAttemptRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const parsed: PipelineEventMessage = JSON.parse(event.data);
          setLatestEvent(parsed);
          setEvents((prev) => {
            const next = [parsed, ...prev];
            return next.slice(0, maxBuffer); // Bounded ring buffer
          });
        } catch {
          // Ignore unparsable payload
        }
      };

      ws.onclose = () => {
        if (!isMountedRef.current) return;
        setConnectionState('CLOSED');
        if (autoReconnect) {
          const delay = Math.min(
            reconnectIntervalMs * Math.pow(1.5, reconnectAttemptRef.current),
            maxReconnectIntervalMs
          );
          reconnectAttemptRef.current += 1;
          reconnectTimeoutRef.current = window.setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch {
      if (autoReconnect && isMountedRef.current) {
        reconnectTimeoutRef.current = window.setTimeout(connect, reconnectIntervalMs);
      }
    }
  }, [url, autoReconnect, reconnectIntervalMs, maxReconnectIntervalMs, maxBuffer]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  return {
    events,
    latestEvent,
    connectionState,
    clearEvents,
  };
}
