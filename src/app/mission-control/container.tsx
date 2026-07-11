import { useState, useEffect, useCallback, useRef } from 'react'

import { readControlYaml, readStateJson } from '@/lib/ledger-reader'
import { type MissionControlData, MissionControlView } from '.'
import type { GateStats } from './gate-flow'
import type { TickerEvent } from './live-ticker'
import type { TickReport } from './tick-summary'
import type { WorkerInfo } from './worker-status'

/**
 * Fetches AlphaForge ledger data and feeds it to MissionControlView.
 * Reads control.yaml + state.json via the gateway's file API.
 */
export function MissionControlContainer() {
  const [data, setData] = useState<MissionControlData | null>(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [control, state] = await Promise.all([
        readControlYaml(),
        readStateJson(),
      ])

      if (!state) {
        setLoading(false)
        return
      }

      const openHyps = 0 // state.json doesn't track hypothesis counts
      const branches = state.worker_status || {}
      const branchCount = Object.keys(branches).length

      const tick: TickReport = {
        tick_number: state.current_tick,
        date: state.last_updated || new Date().toISOString(),
        budget_spent: state.total_budget_spent,
        workers_active: branchCount,
        hypotheses_created: openHyps,
        hypotheses_completed: 0,
        gates_passed: Object.values(state.gates).reduce((sum, v) => sum + v, 0),
        summary_text: `Tick #${state.current_tick}. Gates: T0=${state.gates.T0} T1=${state.gates.T1} T2=${state.gates.T2} T3=${state.gates.T3}.`,
      }

      const workers: WorkerInfo[] = Object.entries(branches).map(([name, status]) => ({
        id: name,
        name,
        status: status === 'running' ? 'running' as const
          : status === 'failed' ? 'failed' as const
          : 'idle' as const,
        progress: status === 'running' ? 0.5 : status === 'completed' ? 1 : 0,
        current_task: status,
      }))

      const gates: GateStats = {
        T0: { pass_count: state.gates.T0, fail_count: 0, last_transition: state.last_updated },
        T1: { pass_count: state.gates.T1, fail_count: 0, last_transition: state.last_updated },
        T2: { pass_count: state.gates.T2, fail_count: 0, last_transition: state.last_updated },
        T3: { pass_count: state.gates.T3, fail_count: 0, last_transition: state.last_updated },
      }

      const events: TickerEvent[] = [
        {
          id: `tick-${state.current_tick}`,
          timestamp: state.last_updated || new Date().toISOString(),
          type: 'info',
          message: `Tick #${state.current_tick} — $${state.total_budget_spent.toFixed(2)} spent`,
        },
      ]

      setData({
        tick,
        workers,
        gates,
        events,
        budgetSpent: state.total_budget_spent,
        budgetTotal: control?.budget_usd || 25,
        loading: false,
      })
      setLoading(false)
    } catch (err) {
      console.warn('[MissionControlContainer] Failed to load ledger:', err)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, 15000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [refresh])

  const mcData: MissionControlData = data || {
    tick: null,
    workers: [],
    gates: {
      T0: { pass_count: 0, fail_count: 0, last_transition: null },
      T1: { pass_count: 0, fail_count: 0, last_transition: null },
      T2: { pass_count: 0, fail_count: 0, last_transition: null },
      T3: { pass_count: 0, fail_count: 0, last_transition: null },
    },
    events: [],
    budgetSpent: 0,
    budgetTotal: 25,
    loading,
  }

  return <MissionControlView {...mcData} />
}
