import { useCallback, useEffect, useState } from 'react'

import { PAGE_INSET_X, PAGE_MAX_W } from '@/app/layout-constants'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { readControlYaml, writeControlYaml, type ControlConfig } from '@/lib/ledger-reader'
import { HumanInstructionEditor, type InstructionEntry } from './human-instruction'
import { PathEditor } from './path-editor'

type ViewState = 'loading' | 'empty' | 'error' | 'data'

const MODES = ['auto', 'manual', 'paused'] as const
type Mode = (typeof MODES)[number]

export function ControlPlaneView() {
  const [viewState, setViewState] = useState<ViewState>('loading')
  const [error, setError] = useState<string | null>(null)

  const [mode, setMode] = useState<Mode>('auto')
  const [budget, setBudget] = useState('25')
  const [parallelWorkers, setParallelWorkers] = useState('3')
  const [instruction, setInstruction] = useState('')
  const [allowedPaths, setAllowedPaths] = useState<string[]>([])
  const [forbiddenPaths, setForbiddenPaths] = useState<string[]>([])
  const [lastSaved, setLastSaved] = useState<string | null>(null)
  const [instructionHistory, setInstructionHistory] = useState<InstructionEntry[]>([])

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [touched, setTouched] = useState(false)

  // Load real control.yaml on mount
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const config = await readControlYaml()
        if (cancelled) return
        if (!config) {
          setViewState('empty')
          return
        }
        setMode(config.mode)
        setBudget(String(config.budget_usd))
        setParallelWorkers(String(config.parallel_workers))
        setInstruction(config.human_instruction)
        setAllowedPaths(config.allowed_paths)
        setForbiddenPaths(config.forbidden_paths)
        setViewState('data')
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setViewState('error')
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const budgetNum = budget === '' ? NaN : Number(budget)
  const workersNum = parallelWorkers === '' ? NaN : Number(parallelWorkers)

  const budgetError =
    touched && (isNaN(budgetNum) || budgetNum <= 0) ? 'Must be greater than 0' : null
  const workersError =
    touched && (isNaN(workersNum) || workersNum < 1 || workersNum > 10)
      ? 'Must be between 1 and 10' : null
  const modeError = touched && !mode ? 'Mode is required' : null
  const isValid = !budgetError && !workersError && !modeError && mode !== undefined

  const handleSave = useCallback(async () => {
    setTouched(true)
    if (!isValid) return
    const config: ControlConfig = {
      mode, budget_usd: budgetNum, parallel_workers: workersNum,
      human_instruction: instruction, allowed_paths: allowedPaths,
      forbidden_paths: forbiddenPaths,
    }
    setSaving(true)
    setSaveError(null)
    try {
      await writeControlYaml(config)
      setLastSaved(new Date().toLocaleString())
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }, [isValid, mode, budgetNum, workersNum, instruction, allowedPaths, forbiddenPaths])

  const handleTickNow = useCallback(async () => {
    try {
      if (typeof window !== 'undefined' && (window as any).__HERMES_RPC__) {
        await (window as any).__HERMES_RPC__('cron.run', { jobName: 'af-orchestrator-tick' })
      }
    } catch { /* Tick Now is best-effort */ }
  }, [])

  if (viewState === 'loading') {
    return (
      <div className={cn('flex h-full flex-col overflow-y-auto', PAGE_INSET_X)}>
        <div className={cn('mx-auto flex w-full flex-col gap-6 py-6', PAGE_MAX_W)}>
          <div><Skeleton className="mb-2 h-6 w-48" /><Skeleton className="h-4 w-96" /></div>
          <div className="space-y-4 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-6">
            <Skeleton className="h-5 w-32" /><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (viewState === 'error') {
    return (
      <div className={cn('flex h-full flex-col overflow-y-auto', PAGE_INSET_X)}>
        <div className={cn('mx-auto flex w-full flex-col gap-6 py-6', PAGE_MAX_W)}>
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-red-500/30 bg-(--ui-editor-surface-background) px-6 py-12">
            <Codicon className="text-red-500" name="error" size="2rem" />
            <p className="text-sm font-medium">Failed to load config</p>
            <p className="max-w-md text-center text-xs text-muted-foreground">{error || 'control.yaml could not be loaded.'}</p>
            <Button onClick={() => window.location.reload()} size="sm" variant="outline">
              <Codicon name="refresh" size="0.875rem" /> Try again
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (viewState === 'empty') {
    return (
      <div className={cn('flex h-full flex-col overflow-y-auto', PAGE_INSET_X)}>
        <div className={cn('mx-auto flex w-full flex-col gap-6 py-6', PAGE_MAX_W)}>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Control Plane</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Orchestrator configuration — reads/writes <code className="rounded bg-(--ui-editor-surface-background) px-1 py-0.5 text-xs">control.yaml</code>
            </p>
          </div>
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) px-6 py-12">
            <Codicon className="text-muted-foreground" name="new-file" size="2rem" />
            <p className="text-sm font-medium">No config yet</p>
            <p className="max-w-md text-center text-xs text-muted-foreground">
              Create the initial <code className="rounded bg-(--ui-editor-surface-background) px-1 py-0.5 text-[0.6875rem]">control.yaml</code> to configure the orchestrator.
            </p>
            <Button onClick={() => { setMode('auto'); setBudget('25'); setParallelWorkers('3'); setViewState('data') }} size="sm" variant="default">
              <Codicon name="add" size="0.875rem" /> Create config
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Data view
  return (
    <div className={cn('flex h-full flex-col overflow-y-auto', PAGE_INSET_X)}>
      <div className={cn('mx-auto flex w-full flex-col gap-6 py-6', PAGE_MAX_W)}>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Control Plane</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Orchestrator configuration — reads/writes{' '}
            <code className="rounded bg-(--ui-editor-surface-background) px-1 py-0.5 text-xs">control.yaml</code>
          </p>
        </div>

        <section className="space-y-6 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-6">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Codicon name="settings-gear" size="1rem" /> Settings
          </h2>

          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Codicon name="debug" size="0.875rem" /> Mode
            </label>
            <Select onValueChange={(v) => { setMode(v as Mode); setTouched(true) }} value={mode}>
              <SelectTrigger><SelectValue placeholder="Select mode" /></SelectTrigger>
              <SelectContent>
                {MODES.map((m) => (<SelectItem key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</SelectItem>))}
              </SelectContent>
            </Select>
            {modeError && <p className="text-[0.6875rem] text-red-500">{modeError}</p>}
          </div>

          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Codicon name="dollar" size="0.875rem" /> Max Budget
            </label>
            <Input min={1} onChange={(e) => { setBudget(e.target.value); setTouched(true) }} placeholder="e.g. 25" type="number" value={budget} />
            {budgetError && <p className="text-[0.6875rem] text-red-500">{budgetError}</p>}
          </div>

          <div className="space-y-1.5">
            <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Codicon name="hubot" size="0.875rem" /> Parallel Workers
            </label>
            <Input max={10} min={1} onChange={(e) => { setParallelWorkers(e.target.value); setTouched(true) }} placeholder="e.g. 3" type="number" value={parallelWorkers} />
            {workersError && <p className="text-[0.6875rem] text-red-500">{workersError}</p>}
          </div>
        </section>

        <section className="space-y-3 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-6">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Codicon name="comment" size="1rem" /> Human Instruction
          </h2>
          <HumanInstructionEditor history={instructionHistory} instruction={instruction} loading={false} onChange={setInstruction} />
        </section>

        <section className="space-y-3 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-6">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Codicon name="file-directory" size="1rem" /> Path Rules
          </h2>
          <PathEditor allowedPaths={allowedPaths} forbiddenPaths={forbiddenPaths} loading={false} onChange={(allowed, forbidden) => { setAllowedPaths(allowed); setForbiddenPaths(forbidden); setTouched(true) }} />
        </section>

        <div className="flex items-center justify-between gap-4 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) px-6 py-4">
          <div className="flex items-center gap-3">
            <p className="text-xs text-muted-foreground">Last saved: {lastSaved ?? 'never'}</p>
            {saveError && <p className="text-xs text-red-500">{saveError}</p>}
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={handleTickNow} size="sm" variant="outline">
              <Codicon name="play" size="0.875rem" /> Tick Now
            </Button>
            <Button disabled={saving || (touched && !isValid)} onClick={handleSave} size="sm" variant="default">
              <Codicon name="save" size="0.875rem" /> {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
