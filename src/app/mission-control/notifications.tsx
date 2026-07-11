import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { SectionCard } from '@/components/ui/section-card'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface NotificationRule {
  id: string
  type: 'budget_threshold' | 't4_pending' | 'tick_fail' | 'goal_achieved' | 'no_progress'
  enabled: boolean
  cooldown_minutes: number
  last_fired: string | null
}

interface NotificationEvent {
  id: string
  type: string
  message: string
  timestamp: string
  read: boolean
}

// ── Hook ───────────────────────────────────────────────────────────────────

const DEFAULT_RULES: NotificationRule[] = [
  { id: 'budget', type: 'budget_threshold', enabled: true, cooldown_minutes: 30, last_fired: null },
  { id: 't4', type: 't4_pending', enabled: true, cooldown_minutes: 5, last_fired: null },
  { id: 'tick_fail', type: 'tick_fail', enabled: true, cooldown_minutes: 10, last_fired: null },
  { id: 'goal', type: 'goal_achieved', enabled: true, cooldown_minutes: 0, last_fired: null },
  { id: 'progress', type: 'no_progress', enabled: true, cooldown_minutes: 60, last_fired: null },
]

const RULE_LABELS: Record<string, string> = {
  budget_threshold: 'Budget threshold',
  t4_pending: 'T4 approval pending',
  tick_fail: 'Tick failure',
  goal_achieved: 'Goal achieved',
  no_progress: 'No progress (3 ticks)',
}

// ── Component ───────────────────────────────────────────────────────────────

export function NotificationPanel() {
  const [rules, setRules] = useState<NotificationRule[]>(DEFAULT_RULES)
  const [recentEvents, setRecentEvents] = useState<NotificationEvent[]>([])

  const toggleRule = useCallback((id: string) => {
    setRules(prev => prev.map(r => r.id === id ? { ...r, enabled: !r.enabled } : r))
  }, [])

  return (
    <SectionCard title="Notifications">
      <div className="space-y-2">
        {rules.map(rule => (
          <div key={rule.id} className="flex items-center justify-between rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-3 py-2">
            <div className="flex items-center gap-2">
              <Codicon className={cn('size-3.5', rule.enabled ? 'text-green-400' : 'text-muted-foreground')} name="bell" />
              <span className="text-xs text-foreground">{RULE_LABELS[rule.type]}</span>
            </div>
            <button
              className={cn('rounded px-2 py-0.5 text-[10px] font-medium transition-colors',
                rule.enabled ? 'bg-green-500/20 text-green-400' : 'bg-muted/30 text-muted-foreground'
              )}
              onClick={() => toggleRule(rule.id)}
              type="button"
            >
              {rule.enabled ? 'ON' : 'OFF'}
            </button>
          </div>
        ))}
      </div>

      {recentEvents.length > 0 && (
        <div className="mt-3 space-y-1 border-t border-(--ui-stroke-tertiary) pt-3">
          <p className="text-[10px] font-medium uppercase text-muted-foreground">Recent</p>
          {recentEvents.slice(0, 5).map(evt => (
            <p key={evt.id} className="text-[11px] text-muted-foreground">
              {evt.message}
            </p>
          ))}
        </div>
      )}
    </SectionCard>
  )
}
