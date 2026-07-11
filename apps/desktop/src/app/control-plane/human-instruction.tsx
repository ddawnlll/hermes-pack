import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export interface InstructionEntry {
  text: string
  timestamp: string
  author: string
}

export interface HumanInstructionEditorProps {
  instruction: string
  onChange: (val: string) => void
  history: InstructionEntry[]
  loading: boolean
}

export function HumanInstructionEditor({
  instruction,
  onChange,
  history,
  loading
}: HumanInstructionEditorProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-44" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <Textarea
        className="min-h-24 font-mono text-xs leading-5"
        onChange={(e) => onChange(e.target.value)}
        placeholder="Write instructions for the orchestrator…"
        value={instruction}
      />

      <div className="flex items-center gap-2">
        <Button onClick={() => onChange(instruction)} size="sm" variant="default">
          <Codicon name="save" size="0.875rem" />
          Save
        </Button>
        <Button
          disabled={!instruction}
          onClick={() => onChange('')}
          size="sm"
          variant="text"
        >
          Clear
        </Button>
      </div>

      {history.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">History</p>
          <div className="space-y-1">
            {history.map((entry, i) => (
              <div
                className={cn(
                  'flex items-start gap-2 rounded-md border border-(--ui-stroke-tertiary) px-3 py-2',
                  'bg-(--ui-editor-surface-background)'
                )}
                key={i}
              >
                <Codicon className="mt-0.5 shrink-0 text-muted-foreground" name="comment" size="0.875rem" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs leading-5">{entry.text}</p>
                  <p className="text-[0.6875rem] text-muted-foreground">
                    {entry.author} · {entry.timestamp}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
