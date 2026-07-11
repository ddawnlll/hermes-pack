import { useCallback, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

export interface WorkerControlInfo {
  id: string
  name: string
  status: 'running' | 'idle' | 'failed' | 'stopped'
}

// ── Props ───────────────────────────────────────────────────────────────────

interface WorkerControlsProps {
  workers: WorkerControlInfo[]
  onStop?: (workerId: string, force: boolean) => void
}

// ── Component ───────────────────────────────────────────────────────────────

export function WorkerControls({ workers, onStop }: WorkerControlsProps) {
  const runningWorkers = workers.filter(w => w.status === 'running')

  if (runningWorkers.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {runningWorkers.map(worker => (
        <WorkerStopButton
          key={worker.id}
          worker={worker}
          onStop={onStop}
        />
      ))}
    </div>
  )
}

// ── Worker Stop Button (two-stage: soft → force) ────────────────────────────

function WorkerStopButton({
  worker,
  onStop,
}: {
  worker: WorkerControlInfo
  onStop?: (workerId: string, force: boolean) => void
}) {
  const [stage, setStage] = useState<'idle' | 'confirm-soft' | 'confirm-force'>('idle')

  const handleSoftStop = useCallback(() => {
    if (stage === 'confirm-soft') {
      onStop?.(worker.id, false)
      setStage('idle')
    } else {
      setStage('confirm-soft')
    }
  }, [stage, worker.id, onStop])

  const handleForceStop = useCallback(() => {
    if (stage === 'confirm-force') {
      onStop?.(worker.id, true)
      setStage('idle')
    } else {
      setStage('confirm-force')
    }
  }, [stage, worker.id, onStop])

  const handleCancel = useCallback(() => setStage('idle'), [])

  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-bg-quaternary) px-2 py-1.5">
      <Codicon className="size-3.5 text-green-400" name="play" />
      <span className="text-xs font-medium text-foreground">{worker.name}</span>

      {stage === 'idle' ? (
        <Button onClick={handleSoftStop} size="sm" variant="ghost" className="h-6 px-1.5">
          <Codicon className="size-3 text-muted-foreground" name="debug-stop" />
        </Button>
      ) : stage === 'confirm-soft' ? (
        <div className="flex items-center gap-1">
          <Button onClick={handleSoftStop} size="sm" variant="outline" className="h-6 px-1.5 text-amber-400">
            <Codicon className="size-3" name="warning" /> Stop
          </Button>
          <Button onClick={handleForceStop} size="sm" variant="outline" className="h-6 px-1.5 text-red-400">
            Force
          </Button>
          <Button onClick={handleCancel} size="sm" variant="ghost" className="h-6 px-1.5">
            <Codicon className="size-3" name="close" />
          </Button>
        </div>
      ) : (
        <div className="flex items-center gap-1">
          <Button onClick={handleForceStop} size="sm" variant="outline" className="h-6 px-1.5 text-red-400">
            <Codicon className="size-3" name="error" /> Kill
          </Button>
          <Button onClick={handleCancel} size="sm" variant="ghost" className="h-6 px-1.5">
            <Codicon className="size-3" name="close" />
          </Button>
        </div>
      )}
    </div>
  )
}
