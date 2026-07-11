import { useEffect, useState } from 'react'

import { PAGE_INSET_X, PAGE_MAX_W } from '@/app/layout-constants'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { LiveBadge } from '@/components/ui/live-badge'
import { MeterBar } from '@/components/ui/meter-bar'
import { SectionCard } from '@/components/ui/section-card'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusDot } from '@/components/ui/status-dot'
import { cn } from '@/lib/utils'

import { readControlYaml, readStateJson, type ControlConfig, type OrchestratorState } from '@/lib/ledger-reader'

interface ProjectCard {
  id: string
  name: string
  status: 'healthy' | 'attention' | 'critical'
  mode: 'auto' | 'supervised' | 'paused'
  current_tick: number
  budget_spent: number
  budget_total: number
  open_hypotheses: number
  last_event: string
  last_event_time: string
  pending_gate?: string
}

function ProjectCardView({ project }: { project: ProjectCard }) {
  const statusDot: 'active' | 'idle' | 'warning' | 'error' =
    project.status === 'healthy' ? 'active' : project.status === 'attention' ? 'warning' : 'error'

  const meterVariant =
    project.budget_spent / project.budget_total > 0.9 ? 'danger'
    : project.budget_spent / project.budget_total > 0.7 ? 'warning'
    : 'default'

  return (
    <SectionCard className="cursor-pointer transition-all hover:border-(--ui-stroke-secondary) hover:shadow-nous">
      <div className="space-y-3">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-bold text-foreground">{project.name}</h3>
            <div className="mt-1 flex items-center gap-2">
              <StatusDot pulse={project.status !== 'healthy'} status={statusDot} />
              <span className="text-xs capitalize text-muted-foreground">{project.status}</span>
              <LiveBadge variant={project.mode === 'auto' ? 'success' : 'default'}>
                {project.mode}
              </LiveBadge>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm font-bold tabular-nums text-foreground">
              Tick {project.current_tick}
            </div>
            {project.pending_gate && (
              <span className="mt-0.5 inline-block rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-400">
                {project.pending_gate} pending
              </span>
            )}
          </div>
        </div>

        <div>
          <MeterBar
            max={project.budget_total}
            showLabel
            value={project.budget_spent}
            variant={meterVariant}
          />
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1">
            <Codicon className="size-3 text-muted-foreground" name="lightbulb" />
            <span className="font-medium text-foreground">{project.open_hypotheses}</span>
            <span className="text-muted-foreground">open</span>
          </div>
          <span className="text-muted-foreground">{project.last_event_time}</span>
        </div>

        <div className="rounded bg-(--ui-bg-quaternary) px-2 py-1.5 text-xs text-muted-foreground">
          {project.last_event}
        </div>
      </div>
    </SectionCard>
  )
}

export function PortfolioView() {
  const [projects, setProjects] = useState<ProjectCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function loadProjects() {
      try {
        const [control, state] = await Promise.all([
          readControlYaml(),
          readStateJson(),
        ])
        if (cancelled) return

        if (!control && !state) {
          setProjects([])
          setLoading(false)
          return
        }

        // Build project card from available data
        const hasFailures = state && Object.values(state.worker_status).includes('failed')
        const project: ProjectCard = {
          id: 'alphaforge',
          name: 'AlphaForge',
          status: hasFailures ? 'critical' : 'healthy',
          mode: control?.mode === 'paused' ? 'paused' : control?.mode === 'manual' ? 'supervised' : 'auto',
          current_tick: state?.current_tick ?? 0,
          budget_spent: state?.total_budget_spent ?? 0,
          budget_total: control?.budget_usd ?? 25,
          open_hypotheses: 0,
          last_event: hasFailures ? 'Worker failure detected' : `Tick ${state?.current_tick ?? 0}`,
          last_event_time: state?.last_updated ? new Date(state.last_updated).toLocaleTimeString() : 'unknown',
        }

        setProjects([project])
        setLoading(false)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }
    loadProjects()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-(--ui-stroke-tertiary) px-6 py-4">
          <div><Skeleton className="h-6 w-32" /><Skeleton className="mt-1 h-4 w-48" /></div>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-48 rounded-lg" />
            <Skeleton className="h-48 rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-(--ui-stroke-tertiary) px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">Portfolio</h1>
          <p className="text-sm text-muted-foreground">Active orchestrator projects</p>
        </div>
        <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
          <Codicon className="size-3.5" name="refresh" />
          Refresh
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) px-6 py-16">
            <Codicon className="text-muted-foreground" name="folder-open" size="3rem" />
            <p className="text-sm font-medium text-foreground">No projects found</p>
            <p className="max-w-md text-center text-xs text-muted-foreground">
              Bootstrap a project with <code className="rounded bg-(--ui-bg-quaternary) px-1 py-0.5 text-[0.6875rem]">hermes-pack bootstrap</code> or add an adapter in <code className="rounded bg-(--ui-bg-quaternary) px-1 py-0.5 text-[0.6875rem]">adapters/</code>
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {projects.map(project => (
              <ProjectCardView key={project.id} project={project} />
            ))}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-xs text-red-400">
            Error loading projects: {error}
          </div>
        )}
      </div>
    </div>
  )
}
