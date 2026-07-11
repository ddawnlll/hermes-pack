import { Codicon } from '@/components/ui/codicon'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/ui/status-dot'
import { relativeTime } from '@/lib/time'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface GateInfo {
  pass_count: number
  fail_count: number
  last_transition: string | null
}

export interface GateStats {
  T0: GateInfo
  T1: GateInfo
  T2: GateInfo
  T3: GateInfo
}

export interface HypothesisCard {
  id: string
  statement: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  current_gate: 'praxis' | 'T1' | 'T2' | 'T3' | 'T4' | 'merged' | 'rejected'
  evidence_path?: string
  created_at: string
}

// ── Props ───────────────────────────────────────────────────────────────────

interface GateFlowProps {
  gates: GateStats
  loading: boolean
  hypotheses?: HypothesisCard[]
}

// ── Constants ───────────────────────────────────────────────────────────────

const GATE_ORDER = ['T0', 'T1', 'T2', 'T3'] as const

const GATE_LABELS: Record<string, string> = {
  T0: 'Praxis',
  T1: 'Validate',
  T2: 'Deploy',
  T3: 'Production',
  T4: 'Human',
}

const HYPOTHESIS_GATES = ['praxis', 'T1', 'T2', 'T3', 'T4'] as const

const GATE_COLORS: Record<string, string> = {
  praxis: 'border-purple-500/30 bg-purple-500/5',
  T1: 'border-blue-500/30 bg-blue-500/5',
  T2: 'border-amber-500/30 bg-amber-500/5',
  T3: 'border-green-500/30 bg-green-500/5',
  T4: 'border-red-500/30 bg-red-500/5',
  merged: 'border-green-500/50 bg-green-500/10',
  rejected: 'border-red-500/50 bg-red-500/10',
}

const RISK_DOT: Record<string, 'active' | 'idle' | 'warning' | 'error'> = {
  low: 'idle',
  medium: 'active',
  high: 'warning',
  critical: 'error',
}

// ── Component ───────────────────────────────────────────────────────────────

export function GateFlow({ gates, loading, hypotheses = [] }: GateFlowProps) {
  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Gate Flow
      </h2>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="space-y-1" key={i}>
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-3 w-20" />
            </div>
          ))}
        </div>
      ) : hypotheses.length > 0 ? (
        /* Hypothesis-based pipeline view */
        <div className="space-y-4">
          {/* Gate columns header */}
          <div className="grid grid-cols-5 gap-2">
            {HYPOTHESIS_GATES.map(gate => (
              <div key={gate} className="text-center">
                <span className="text-[10px] font-medium uppercase text-muted-foreground">
                  {GATE_LABELS[gate] ?? gate}
                </span>
              </div>
            ))}
          </div>

          {/* Hypothesis cards */}
          <div className="space-y-2">
            {hypotheses.map(hyp => (
              <HypothesisRow key={hyp.id} hypothesis={hyp} />
            ))}
          </div>
        </div>
      ) : (
        /* Fallback: aggregate counts */
        <div className="flex flex-col gap-1.5">
          {GATE_ORDER.map((key, idx) => {
            const gate = gates[key as keyof GateStats] as GateInfo | undefined
            if (!gate) return null

            const total = gate.pass_count + gate.fail_count
            const passRate = total > 0 ? (gate.pass_count / total) * 100 : 0
            const lastLabel = gate.last_transition
              ? relativeTime(new Date(gate.last_transition).getTime())
              : '—'

            return (
              <div key={key}>
                <div className="rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background)/60 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">
                      {GATE_LABELS[key]} — {key}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{lastLabel}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Codicon className="size-3 text-green-400" name="pass" />
                      {gate.pass_count}
                    </span>
                    <span className="flex items-center gap-1">
                      <Codicon className="size-3 text-red-400" name="error" />
                      {gate.fail_count}
                    </span>
                    <span className={cn('ml-auto font-medium tabular-nums',
                      passRate >= 80 ? 'text-green-400' : passRate >= 50 ? 'text-yellow-400' : 'text-red-400'
                    )}>
                      {passRate.toFixed(0)}%
                    </span>
                  </div>
                </div>
                {idx < GATE_ORDER.length - 1 && (
                  <div className="flex justify-center py-0.5">
                    <Codicon className="size-3.5 text-muted-foreground/50" name="arrow-down" />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Hypothesis Row ──────────────────────────────────────────────────────────

function HypothesisRow({ hypothesis }: { hypothesis: HypothesisCard }) {
  const currentIdx = HYPOTHESIS_GATES.indexOf(hypothesis.current_gate as any)

  return (
    <div className="flex items-center gap-2 rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-3 py-2">
      {/* Risk dot */}
      <StatusDot status={RISK_DOT[hypothesis.risk_level] ?? 'idle'} />

      {/* Statement */}
      <div className="flex-1 min-w-0">
        <p className="truncate text-xs font-medium text-foreground">{hypothesis.statement}</p>
        {hypothesis.evidence_path && (
          <p className="mt-0.5 truncate text-[10px] text-muted-foreground">
            <Codicon className="size-2.5 inline" name="file" /> {hypothesis.evidence_path}
          </p>
        )}
      </div>

      {/* Gate pipeline indicator */}
      <div className="flex items-center gap-1">
        {HYPOTHESIS_GATES.map((gate, idx) => {
          const isActive = idx === currentIdx
          const isPast = idx < currentIdx
          return (
            <div key={gate} className="flex items-center gap-0.5">
              <div className={cn(
                'size-2 rounded-full transition-colors',
                isActive ? 'bg-foreground ring-2 ring-foreground/20' :
                isPast ? 'bg-green-400' : 'bg-muted/30'
              )} />
              {idx < HYPOTHESIS_GATES.length - 1 && (
                <div className={cn('h-px w-2', isPast ? 'bg-green-400' : 'bg-muted/30')} />
              )}
            </div>
          )
        })}
      </div>

      {/* Gate label */}
      <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', GATE_COLORS[hypothesis.current_gate] ?? 'bg-muted/10')}>
        {hypothesis.current_gate}
      </span>
    </div>
  )
}
