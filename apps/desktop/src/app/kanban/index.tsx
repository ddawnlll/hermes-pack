import { useEffect, useState } from 'react'

import { PAGE_INSET_X, PAGE_MAX_W } from '@/app/layout-constants'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/ui/status-dot'
import { cn } from '@/lib/utils'
import { readControlYaml, readStateJson } from '@/lib/ledger-reader'

interface KanbanTask {
  id: string
  title: string
  status: 'backlog' | 'ready' | 'in_progress' | 'review' | 'done'
  assignee?: string
  priority: 'low' | 'medium' | 'high'
  created_at: string
}

const COLUMNS = ['backlog', 'ready', 'in_progress', 'review', 'done'] as const
const COLUMN_LABELS: Record<string, string> = {
  backlog: 'Backlog', ready: 'Ready', in_progress: 'In Progress', review: 'Review', done: 'Done',
}

export function KanbanView() {
  const [tasks, setTasks] = useState<KanbanTask[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const state = await readStateJson()
        if (cancelled) return
        // Build tasks from state data
        const workers = state?.worker_status ?? {}
        const initial: KanbanTask[] = Object.entries(workers).map(([name, status], i) => ({
          id: `task-${i}`,
          title: name,
          status: status === 'running' ? 'in_progress' : status === 'completed' ? 'done' : status === 'failed' ? 'review' : 'backlog',
          assignee: name,
          priority: status === 'failed' ? 'high' : 'medium',
          created_at: state?.last_updated ?? new Date().toISOString(),
        }))
        setTasks(initial.length > 0 ? initial : [])
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
          <h1 className="text-xl font-semibold tracking-tight">Kanban</h1>
          <p className="text-sm text-muted-foreground">AlphaForge task board</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
          <Codicon className="size-3.5" name="refresh" /> Refresh
        </Button>
      </div>

      <div className="flex-1 overflow-x-auto px-6 py-4">
        {loading ? (
          <div className="grid grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2"><Skeleton className="h-6 w-20" /><Skeleton className="h-24 w-full rounded" /></div>
            ))}
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-(--ui-stroke-tertiary) py-16">
            <Codicon className="text-muted-foreground" name="project" size="2rem" />
            <p className="text-sm text-muted-foreground">No tasks yet. Tasks appear when workers create them.</p>
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-4 min-w-[800px]">
            {COLUMNS.map(col => {
              const colTasks = tasks.filter(t => t.status === col)
              return (
                <div key={col} className="space-y-2">
                  <div className="flex items-center gap-2 pb-2">
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground">{COLUMN_LABELS[col]}</h3>
                    <span className="rounded bg-muted/30 px-1.5 py-0.5 text-[10px] text-muted-foreground">{colTasks.length}</span>
                  </div>
                  {colTasks.map(task => (
                    <div key={task.id} className="rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) p-2.5 space-y-1.5">
                      <p className="text-xs font-medium text-foreground">{task.title}</p>
                      <div className="flex items-center gap-2">
                        <StatusDot status={task.priority === 'high' ? 'warning' : 'idle'} />
                        <span className="text-[10px] text-muted-foreground">{task.priority}</span>
                        {task.assignee && <span className="text-[10px] text-muted-foreground ml-auto">{task.assignee}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
