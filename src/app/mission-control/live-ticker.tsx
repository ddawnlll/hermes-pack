import { useEffect, useRef } from 'react'

import { Codicon } from '@/components/ui/codicon'
import { Skeleton } from '@/components/ui/skeleton'
import { relativeTime } from '@/lib/time'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface TickerEvent {
  id: string
  timestamp: string
  type: 'info' | 'warning' | 'error' | 'success'
  message: string
}

// ── Props ───────────────────────────────────────────────────────────────────

interface LiveTickerProps {
  events: TickerEvent[]
  loading: boolean
}

// ── Component ───────────────────────────────────────────────────────────────

const EVENT_CONFIG = {
  info: { icon: 'info', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  warning: { icon: 'warning', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  error: { icon: 'error', color: 'text-red-400', bg: 'bg-red-500/10' },
  success: { icon: 'pass', color: 'text-green-400', bg: 'bg-green-500/10' },
} as const

export function LiveTicker({ events, loading }: LiveTickerProps) {
  const listRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [events])

  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Live Ticker
      </h2>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="flex items-start gap-2" key={i}>
              <Skeleton className="mt-0.5 size-3.5 shrink-0 rounded-full" />
              <div className="flex-1 space-y-1">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Codicon className="size-5" name="radio-tower" />
          <span>No events yet</span>
        </div>
      ) : (
        <div
          className="max-h-[280px] space-y-1 overflow-y-auto scroll-smooth"
          ref={listRef}
        >
          {events.map((event) => {
            const cfg = EVENT_CONFIG[event.type]

            return (
              <div
                className={cn(
                  'flex items-start gap-2 rounded-md px-2 py-1.5 text-xs',
                  cfg.bg,
                )}
                key={event.id}
              >
                <Codicon
                  className={cn('mt-0.5 size-3.5 shrink-0', cfg.color)}
                  name={cfg.icon}
                />
                <div className="min-w-0 flex-1">
                  <span className="text-[10px] font-medium text-muted-foreground">
                    <EventTimestamp timestamp={event.timestamp} />
                  </span>
                  <p className="mt-0.5 leading-snug text-foreground/90">
                    {event.message}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Timestamp ───────────────────────────────────────────────────────────────

function EventTimestamp({ timestamp }: { timestamp: string }) {
  const ts = new Date(timestamp).getTime()

  if (!Number.isFinite(ts)) {return <>{'—'}</>}

  return <>{relativeTime(ts)}</>
}
