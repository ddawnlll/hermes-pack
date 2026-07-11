import { useCallback, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { SectionCard } from '@/components/ui/section-card'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface ApprovalItem {
  id: string
  type: 't4_human' | 'budget_override' | 'risk_escalation'
  hypothesis: string
  evidence_summary: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
  status: 'pending' | 'approved' | 'rejected'
}

// ── Props ───────────────────────────────────────────────────────────────────

interface ApprovalQueueProps {
  items: ApprovalItem[]
  loading: boolean
  onApprove?: (id: string, rationale: string) => void
  onReject?: (id: string, rationale: string) => void
}

// ── Component ───────────────────────────────────────────────────────────────

export function ApprovalQueue({ items, loading, onApprove, onReject }: ApprovalQueueProps) {
  const pendingItems = items.filter(i => i.status === 'pending')

  return (
    <SectionCard title="Approval Queue">
      {loading ? (
        <div className="py-4 text-center text-xs text-muted-foreground">Loading...</div>
      ) : pendingItems.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
          <Codicon className="size-5" name="check" />
          <span>No pending approvals</span>
        </div>
      ) : (
        <div className="space-y-3">
          {pendingItems.map(item => (
            <ApprovalRow
              key={item.id}
              item={item}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </div>
      )}
    </SectionCard>
  )
}

// ── Approval Row ────────────────────────────────────────────────────────────

const RISK_COLORS = {
  low: 'text-green-400 bg-green-500/10',
  medium: 'text-amber-400 bg-amber-500/10',
  high: 'text-orange-400 bg-orange-500/10',
  critical: 'text-red-400 bg-red-500/10',
} as const

function ApprovalRow({
  item,
  onApprove,
  onReject,
}: {
  item: ApprovalItem
  onApprove?: (id: string, rationale: string) => void
  onReject?: (id: string, rationale: string) => void
}) {
  const [rationale, setRationale] = useState('')
  const [expanded, setExpanded] = useState(false)

  const handleApprove = useCallback(() => {
    onApprove?.(item.id, rationale)
    setRationale('')
    setExpanded(false)
  }, [item.id, rationale, onApprove])

  const handleReject = useCallback(() => {
    onReject?.(item.id, rationale)
    setRationale('')
    setExpanded(false)
  }, [item.id, rationale, onReject])

  return (
    <div className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium uppercase', RISK_COLORS[item.risk_level])}>
              {item.risk_level}
            </span>
            <span className="text-[10px] text-muted-foreground">{item.type.replace('_', ' ')}</span>
          </div>
          <p className="mt-1 text-xs font-medium text-foreground truncate">{item.hypothesis}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground line-clamp-2">{item.evidence_summary}</p>
        </div>
        <button
          className="shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => setExpanded(!expanded)}
          type="button"
        >
          <Codicon name={expanded ? 'chevron-up' : 'chevron-down'} size="1rem" />
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 border-t border-(--ui-stroke-tertiary) pt-2">
          <textarea
            className="w-full rounded border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground"
            onChange={(e) => setRationale(e.target.value)}
            placeholder="Rationale (optional)..."
            rows={2}
            value={rationale}
          />
          <div className="flex items-center gap-2">
            <Button onClick={handleApprove} size="sm" variant="default">
              <Codicon name="check" size="0.75rem" /> Approve
            </Button>
            <Button onClick={handleReject} size="sm" variant="outline">
              <Codicon name="close" size="0.75rem" /> Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
