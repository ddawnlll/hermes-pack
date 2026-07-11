
import { Codicon } from '@/components/ui/codicon'
import { Skeleton } from '@/components/ui/skeleton'
import { relativeTime } from '@/lib/time'

// ── Types ──────────────────────────────────────────────────────────────────

export interface TickReport {
  tick_number: number
  date: string
  budget_spent: number
  workers_active: number
  hypotheses_created: number
  hypotheses_completed: number
  gates_passed: number
  summary_text: string
}

// ── Props ───────────────────────────────────────────────────────────────────

interface TickSummaryProps {
  tick: TickReport | null
  loading: boolean
}

// ── Component ───────────────────────────────────────────────────────────────

export function TickSummary({ tick, loading }: TickSummaryProps) {
  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Tick Summary
      </h2>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-4 w-32" />
          <div className="flex gap-4">
            <Skeleton className="h-10 w-16" />
            <Skeleton className="h-10 w-16" />
            <Skeleton className="h-10 w-16" />
          </div>
        </div>
      ) : !tick ? (
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Codicon className="size-5" name="broadcast" />
          <span>No tick data yet</span>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Tick number + relative date */}
          <div className="flex items-baseline justify-between">
            <span className="text-lg font-semibold">#{tick.tick_number}</span>
            <RelativeDate date={tick.date} />
          </div>

          {/* Summary text */}
          {tick.summary_text && (
            <p className="text-xs leading-relaxed text-muted-foreground line-clamp-2">
              {tick.summary_text}
            </p>
          )}

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-3">
            <StatCard
              icon="pulse"
              label="Budget"
              value={`$${tick.budget_spent.toFixed(2)}`}
            />
            <StatCard
              icon="beaker"
              label="Hypotheses"
              value={`${tick.hypotheses_completed}/${tick.hypotheses_created}`}
            />
            <StatCard
              icon="pass"
              label="Gates"
              value={String(tick.gates_passed)}
            />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function RelativeDate({ date }: { date: string }) {
  const ts = new Date(date).getTime()
  const label = Number.isFinite(ts) ? relativeTime(ts) : '—'

  return (
    <span className="text-xs text-muted-foreground">{label}</span>
  )
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: string
  label: string
  value: string
}) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background)/50 px-2 py-1.5">
      <Codicon className="size-3.5 text-muted-foreground" name={icon} />
      <span className="text-xs font-medium">{value}</span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  )
}
