import { useCallback, useEffect, useRef, useState } from 'react'

import type { WorkerInfo } from './worker-status'

// ── Types ──────────────────────────────────────────────────────────────────

export interface WorkerLiveUpdate {
  worker_id: string
  current_task?: string
  progress?: number
  status?: WorkerInfo['status']
  timestamp: string
}

// ── Hook: Worker Live Mirroring via Gateway WS ─────────────────────────────

/**
 * Subscribes to gateway WS events for worker profile sessions.
 * Updates worker status cards with live "what they're doing" data.
 */
export function useWorkerLive(initialWorkers: WorkerInfo[]) {
  const [workers, setWorkers] = useState<WorkerInfo[]>(initialWorkers)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Merge live updates into worker list
  const applyUpdate = useCallback((update: WorkerLiveUpdate) => {
    setWorkers(prev => {
      const idx = prev.findIndex(w => w.id === update.worker_id)
      if (idx === -1) return prev

      const updated = [...prev]
      updated[idx] = {
        ...updated[idx],
        current_task: update.current_task ?? updated[idx].current_task,
        progress: update.progress ?? updated[idx].progress,
        status: update.status ?? updated[idx].status,
      }
      return updated
    })
  }, [])

  // Connect to gateway WS for worker events
  useEffect(() => {
    let cancelled = false

    function connect() {
      if (cancelled) return

      try {
        const wsUrl = (window as any).__ENV__?.VITE_GATEWAY_URL?.replace('http', 'ws') ?? 'ws://localhost:9119'
        const ws = new WebSocket(`${wsUrl}/ws/events`)

        ws.onmessage = (event) => {
          if (cancelled) return
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'tool.start' || data.type === 'tool.complete' || data.type === 'message.delta') {
              const update: WorkerLiveUpdate = {
                worker_id: data.session_id ?? 'unknown',
                current_task: data.type === 'tool.start' ? data.tool_name : undefined,
                progress: data.type === 'tool.complete' ? 1.0 : undefined,
                timestamp: data.timestamp ?? new Date().toISOString(),
              }
              applyUpdate(update)
            }
          } catch { /* ignore non-JSON */ }
        }

        ws.onerror = () => {
          ws.close()
          if (!cancelled) {
            reconnectTimer.current = setTimeout(connect, 5000)
          }
        }

        ws.onclose = () => {
          if (!cancelled) {
            reconnectTimer.current = setTimeout(connect, 5000)
          }
        }

        wsRef.current = ws
      } catch {
        // WebSocket not available — silent fallback
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [applyUpdate])

  // Sync when initial workers change
  useEffect(() => {
    setWorkers(initialWorkers)
  }, [initialWorkers])

  return workers
}
