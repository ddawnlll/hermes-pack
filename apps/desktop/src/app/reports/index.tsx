import { useEffect, useState } from 'react'

import { PAGE_INSET_X, PAGE_MAX_W } from '@/app/layout-constants'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { MeterBar } from '@/components/ui/meter-bar'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/ui/status-dot'
import { cn } from '@/lib/utils'
import { readStateJson, type OrchestratorState } from '@/lib/ledger-reader'

interface TickReport {
  tick_number: number
  timestamp: string
  hypothesis?: string
  verdict?: 'pass' | 'fail' | 'pending'
  spend_usd?: number
  gate_results?: Record<string, boolean>
}

export function ReportsView() {
  const [reports, setReports] = useState<TickReport[]>([])
  const [loading, setLoading] = useState(true)
  const [state, setState] = useState<OrchestratorState | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const s = await readStateJson()
        if (cancelled) return
        setState(s)
        // Build reports from state - in real app this would read runs/*.json
        if (s) {
          setReports([{
            tick_number: s.current_tick,
            timestamp: s.last_updated ?? new Date().toISOString(),
            hypothesis: 'Current tick',
            verdict: 'pending',
            spend_usd: s.total_budget_spent,
          }])
        }
        setLoading(false)
      } catch {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex items-center justify-between border-b border-(--ui-stroke-tertiary) px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Reports</h1>
          <p className="text-sm text-muted-foreground">Tick reports & evidence trail</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
          <Codicon className="size-3.5" name="refresh" /> Refresh
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-lg" />)}
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-(--ui-stroke-tertiary) py-16">
            <Codicon className="text-muted-foreground" name="list-flat" size="2rem" />
            <p className="text-sm text-muted-foreground">No tick reports yet. Reports appear after the first orchestrator tick.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Summary */}
            {state && (
              <SectionCard title="Latest Tick Summary">
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-2xl font-bold tabular-nums text-foreground">{state.current_tick}</p>
                    <p className="text-xs text-muted-foreground">Tick</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold tabular-nums text-foreground">${state.total_budget_spent.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground">Spent</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold tabular-nums text-foreground">
                      {Object.values(state.worker_status).filter(s => s === 'running').length}
                    </p>
                    <p className="text-xs text-muted-foreground">Active Workers</p>
                  </div>
                </div>
              </SectionCard>
            )}

            {/* Report list */}
            {reports.map(report => (
              <div key={report.tick_number} className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusDot status={report.verdict === 'pass' ? 'active' : report.verdict === 'fail' ? 'error' : 'idle'} />
                    <span className="text-sm font-medium text-foreground">Tick {report.tick_number}</span>
                    <span className="rounded bg-muted/30 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {new Date(report.timestamp).toLocaleString()}
                    </span>
                  </div>
                  {report.spend_usd !== undefined && (
                    <span className="text-xs text-muted-foreground">${report.spend_usd.toFixed(2)}</span>
                  )}
                </div>
                {report.hypothesis && (
                  <p className="mt-2 text-xs text-muted-foreground">{report.hypothesis}</p>
                )}
                {report.gate_results && (
                  <div className="mt-2 flex gap-2">
                    {Object.entries(report.gate_results).map(([gate, passed]) => (
                      <span key={gate} className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium',
                        passed ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                      )}>
                        {gate}: {passed ? 'PASS' : 'FAIL'}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
