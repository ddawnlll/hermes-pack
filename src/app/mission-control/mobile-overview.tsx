import { Codicon } from '@/components/ui/codicon'
import { LiveBadge } from '@/components/ui/live-badge'
import { MeterBar } from '@/components/ui/meter-bar'
import { StatusDot } from '@/components/ui/status-dot'
import { cn } from '@/lib/utils'

import { type WorkerInfo } from './worker-status'

// ── Types ──────────────────────────────────────────────────────────────────

interface MobileOverviewProps {
  tick?: number
  budgetSpent: number
  budgetTotal: number
  workers: WorkerInfo[]
  goalStatus?: string
  loading: boolean
}

// ── Component ───────────────────────────────────────────────────────────────

/**
 * Mobile-optimized read-only overview.
 * Compact single-column layout with key metrics.
 * No interactive controls (read-only safety).
 */
export function MobileOverview({
  tick = 0,
  budgetSpent,
  budgetTotal,
  workers,
  goalStatus = 'in_progress',
  loading,
}: MobileOverviewProps) {
  if (loading) {
    return (
      <div className="space-y-3 p-4">
        <div className="h-8 w-32 animate-pulse rounded bg-muted/30" />
        <div className="h-20 rounded-lg bg-muted/30" />
        <div className="h-16 rounded-lg bg-muted/30" />
      </div>
    )
  }

  const budgetPct = budgetTotal > 0 ? (budgetSpent / budgetTotal) * 100 : 0
  const activeWorkers = workers.filter(w => w.status === 'running').length

  return (
    <div className="space-y-4 p-4 md:hidden">
      {/* Status header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-foreground">Mission Control</h1>
        <LiveBadge variant={goalStatus === 'achieved' ? 'success' : 'default'}>
          <StatusDot status={goalStatus === 'achieved' ? 'active' : 'idle'} />
          {goalStatus}
        </LiveBadge>
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-3 gap-2">
        <MetricTile label="Tick" value={String(tick)} />
        <MetricTile label="Spent" value={`$${budgetSpent.toFixed(2)}`} />
        <MetricTile label="Workers" value={`${activeWorkers}/${workers.length}`} />
      </div>

      {/* Budget bar */}
      <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-3">
        <MeterBar
          max={budgetTotal}
          showLabel
          value={budgetSpent}
          variant={budgetPct > 90 ? 'danger' : budgetPct > 70 ? 'warning' : 'default'}
        />
      </div>

      {/* Worker list */}
      <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-3">
        <p className="mb-2 text-[10px] font-medium uppercase text-muted-foreground">Workers</p>
        {workers.length === 0 ? (
          <p className="text-xs text-muted-foreground">No workers</p>
        ) : (
          <div className="space-y-1.5">
            {workers.map(w => (
              <div key={w.id} className="flex items-center gap-2">
                <StatusDot status={w.status === 'running' ? 'active' : w.status === 'failed' ? 'error' : 'idle'} />
                <span className="text-xs text-foreground">{w.name}</span>
                <span className="ml-auto text-[10px] text-muted-foreground">{w.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Read-only notice */}
      <p className="text-center text-[10px] text-muted-foreground">
        Read-only view · Use desktop app for controls
      </p>
    </div>
  )
}

// ── Metric Tile ─────────────────────────────────────────────────────────────

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-2 text-center">
      <p className="text-lg font-bold tabular-nums text-foreground">{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  )
}
