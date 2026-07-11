import { Codicon } from '@/components/ui/codicon'
import { MeterBar } from '@/components/ui/meter-bar'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/ui/status-dot'
import { relativeTime } from '@/lib/time'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface TimelineEvent {
  tick_number: number
  timestamp: string
  spend_usd: number
  verdict: 'pass' | 'fail' | 'pending'
  hypothesis?: string
  gate?: string
  metrics?: {
    sharpe?: number
    profit_factor?: number
    r_persistence?: number
    drawdown?: number
  }
}

interface TimelineProps {
  events: TimelineEvent[]
  loading: boolean
  targets?: Record<string, number>
}

// ── Component ───────────────────────────────────────────────────────────────

export function Timeline({ events, loading, targets = {} }: TimelineProps) {
  return (
    <SectionCard title="Timeline">
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3">
              <Skeleton className="size-3 mt-1 rounded-full" />
              <div className="flex-1 space-y-1"><Skeleton className="h-3 w-48" /><Skeleton className="h-2 w-32" /></div>
            </div>
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Codicon className="size-5" name="history" />
          <span>No tick history yet</span>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map((evt, idx) => (
            <TimelineRow key={evt.tick_number} event={evt} targets={targets} isLast={idx === events.length - 1} />
          ))}
        </div>
      )}

      {/* Metric summary */}
      {events.length > 0 && events[0].metrics && (
        <div className="mt-4 border-t border-(--ui-stroke-tertiary) pt-3">
          <p className="mb-2 text-[10px] font-medium uppercase text-muted-foreground">Latest Metrics</p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(events[0].metrics).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between rounded bg-(--ui-bg-quaternary) px-2 py-1">
                <span className="text-[10px] text-muted-foreground">{key.replace(/_/g, ' ')}</span>
                <span className="text-[10px] font-medium tabular-nums text-foreground">{value?.toFixed(2) ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}

// ── Timeline Row ────────────────────────────────────────────────────────────

function TimelineRow({ event, targets, isLast }: { event: TimelineEvent; targets: Record<string, number>; isLast: boolean }) {
  const statusColor = event.verdict === 'pass' ? 'active' : event.verdict === 'fail' ? 'error' : 'idle'

  return (
    <div className="flex gap-3">
      {/* Timeline dot + line */}
      <div className="flex flex-col items-center">
        <StatusDot status={statusColor} />
        {!isLast && <div className="w-px flex-1 bg-(--ui-stroke-tertiary)" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">Tick {event.tick_number}</span>
          <span className="text-[10px] text-muted-foreground">{relativeTime(new Date(event.timestamp).getTime())}</span>
        </div>
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          ${event.spend_usd.toFixed(2)} spent
          {event.gate && <> · {event.gate}</>}
        </p>
        {event.hypothesis && (
          <p className="mt-1 text-[11px] text-muted-foreground line-clamp-1">{event.hypothesis}</p>
        )}
      </div>
    </div>
  )
}
