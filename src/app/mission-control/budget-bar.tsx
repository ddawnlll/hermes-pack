import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

// ── Props ───────────────────────────────────────────────────────────────────

interface BudgetBarProps {
  spent: number
  total: number
  loading: boolean
}

// ── Component ───────────────────────────────────────────────────────────────

export function BudgetBar({ spent, total, loading }: BudgetBarProps) {
  const ratio = total > 0 ? Math.min(spent / total, 1) : 0
  const pct = ratio * 100

  const barColor =
    pct < 70
      ? 'bg-green-500'
      : pct < 90
        ? 'bg-yellow-500'
        : 'bg-red-500'

  const trackBg =
    pct < 70
      ? 'bg-green-500/20'
      : pct < 90
        ? 'bg-yellow-500/20'
        : 'bg-red-500/20'

  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Budget
      </h2>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-3 w-28" />
        </div>
      ) : (
        <div className="space-y-1.5">
          {/* Progress bar */}
          <div
            className={cn('h-3 w-full overflow-hidden rounded-full', trackBg)}
          >
            <div
              className={cn('h-full rounded-full transition-all duration-500', barColor)}
              style={{ width: `${pct}%` }}
            />
          </div>

          {/* Text label */}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              ${spent.toFixed(2)} / ${total.toFixed(2)}
            </span>
            <span className={cn(
              'font-medium tabular-nums',
              pct >= 90 && 'text-red-400',
              pct >= 70 && pct < 90 && 'text-yellow-400',
              pct < 70 && 'text-green-400',
            )}>
              {pct.toFixed(1)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
