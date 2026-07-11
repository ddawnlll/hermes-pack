import { Codicon } from '@/components/ui/codicon'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface WorkerInfo {
  id: string
  name: string
  status: 'running' | 'idle' | 'failed'
  progress: number
  current_task: string
}

// ── Props ───────────────────────────────────────────────────────────────────

interface WorkerStatusProps {
  workers: WorkerInfo[]
  loading: boolean
}

// ── Component ───────────────────────────────────────────────────────────────

export function WorkerStatus({ workers, loading }: WorkerStatusProps) {
  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Worker Status
      </h2>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="space-y-1" key={i}>
              <div className="flex items-center gap-2">
                <Skeleton className="size-3.5 rounded-full" />
                <Skeleton className="h-3.5 w-24" />
              </div>
              <Skeleton className="h-2 w-full" />
              <Skeleton className="h-3 w-32" />
            </div>
          ))}
        </div>
      ) : workers.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Codicon className="size-5" name="person" />
          <span>No workers running</span>
        </div>
      ) : (
        <div className="space-y-3">
          {workers.map((worker) => (
            <WorkerRow key={worker.id} worker={worker} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Worker Row ──────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  running: { icon: 'play', color: 'text-green-400', bg: 'bg-green-500/20' },
  idle: { icon: 'circle', color: 'text-muted-foreground', bg: 'bg-muted/30' },
  failed: { icon: 'error', color: 'text-red-400', bg: 'bg-red-500/20' },
} as const

function WorkerRow({ worker }: { worker: WorkerInfo }) {
  const cfg = STATUS_CONFIG[worker.status]
  const pct = Math.max(0, Math.min(worker.progress * 100, 100))

  return (
    <div className="space-y-1">
      {/* Name + status icon */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Codicon className={cn('size-3.5', cfg.color)} name={cfg.icon} />
          <span className="text-sm font-medium">{worker.name}</span>
        </div>
        <span className={cn('text-[10px] font-medium uppercase', cfg.color)}>
          {worker.status}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted/30">
        <div
          className={cn('h-full rounded-full transition-all duration-300', cfg.bg)}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Current task */}
      {worker.current_task && (
        <p className="truncate text-[11px] text-muted-foreground">
          {worker.current_task}
        </p>
      )}
    </div>
  )
}
