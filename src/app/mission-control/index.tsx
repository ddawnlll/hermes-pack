import { PAGE_INSET_X, PAGE_MAX_W } from '@/app/layout-constants'
import { LiveBadge } from '@/components/ui/live-badge'
import { StatusDot } from '@/components/ui/status-dot'
import { cn } from '@/lib/utils'

import { ApprovalQueue, type ApprovalItem } from './approval-queue'
import { BudgetBar } from './budget-bar'
import { GateFlow, type GateStats } from './gate-flow'
import { LiveTicker, type TickerEvent } from './live-ticker'
import { type TickReport, TickSummary } from './tick-summary'
import { WorkerControls, type WorkerControlInfo } from './worker-controls'
import { type WorkerInfo, WorkerStatus } from './worker-status'

export interface MissionControlData {
  tick?: TickReport | null
  workers?: WorkerInfo[]
  gates?: GateStats
  events?: TickerEvent[]
  budgetSpent?: number
  budgetTotal?: number
  approvals?: ApprovalItem[]
  loading?: boolean
  onApprove?: (id: string, rationale: string) => void
  onReject?: (id: string, rationale: string) => void
  onStopWorker?: (workerId: string, force: boolean) => void
}

const EMPTY_GATES: GateStats = {
  T0: { pass_count: 0, fail_count: 0, last_transition: null },
  T1: { pass_count: 0, fail_count: 0, last_transition: null },
  T2: { pass_count: 0, fail_count: 0, last_transition: null },
  T3: { pass_count: 0, fail_count: 0, last_transition: null },
}

export function MissionControlView({
  tick = null,
  workers = [],
  gates = EMPTY_GATES,
  events = [],
  budgetSpent = 0,
  budgetTotal = 25,
  approvals = [],
  loading = true,
  onApprove,
  onReject,
  onStopWorker,
}: MissionControlData = {}) {
  const connectionText = loading
    ? 'waiting for ledger...'
    : tick
      ? `tick ${tick.tick_number} . live`
      : 'no data'

  const statusDot = loading ? 'warning' : tick ? 'active' : 'warning'

  // Map WorkerInfo to WorkerControlInfo for stop controls
  const controlWorkers: WorkerControlInfo[] = workers.map(w => ({
    id: w.id,
    name: w.name,
    status: w.status,
  }))

  return (
    <div className={cn('flex h-full flex-col overflow-y-auto', PAGE_INSET_X)}>
      <div className={cn('mx-auto flex w-full flex-col gap-6 py-6', PAGE_MAX_W)}>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Mission Control</h1>
            <p className="mt-1 text-sm text-muted-foreground">AlphaForge orchestrator dashboard</p>
          </div>
          <LiveBadge pulse={!loading && !!tick} variant={loading ? 'warning' : tick ? 'success' : 'warning'}>
            <StatusDot pulse={!loading && !!tick} status={statusDot} />
            {connectionText}
          </LiveBadge>
        </div>

        {/* Worker stop controls */}
        {!loading && (
          <WorkerControls workers={controlWorkers} onStop={onStopWorker} />
        )}

        {/* Top row: tick summary + budget + workers */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <TickSummary loading={loading} tick={tick} />
          <BudgetBar loading={loading} spent={budgetSpent} total={budgetTotal} />
          <WorkerStatus loading={loading} workers={workers} />
        </div>

        {/* Approval Queue (T4 Human Gate) */}
        <ApprovalQueue
          items={approvals}
          loading={loading}
          onApprove={onApprove}
          onReject={onReject}
        />

        {/* Middle: gate flow */}
        <GateFlow gates={gates} loading={loading} />

        {/* Bottom: live ticker */}
        <LiveTicker events={events} loading={loading} />
      </div>
    </div>
  )
}
