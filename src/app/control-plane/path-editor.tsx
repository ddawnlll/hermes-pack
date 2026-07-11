import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface PathEditorProps {
  allowedPaths: string[]
  forbiddenPaths: string[]
  onChange: (allowed: string[], forbidden: string[]) => void
  loading: boolean
}

function PathColumn({
  label,
  icon,
  paths,
  onAdd,
  onRemove,
  accentClass,
  emptyText
}: {
  label: string
  icon: string
  paths: string[]
  onAdd: (val: string) => void
  onRemove: (idx: number) => void
  accentClass: string
  emptyText: string
}) {
  const [input, setInput] = useState('')

  const handleAdd = () => {
    const trimmed = input.trim()

    if (!trimmed) {return}
    onAdd(trimmed)
    setInput('')
  }

  return (
    <div className="flex flex-col gap-2">
      <div className={cn('flex items-center gap-1.5 text-xs font-medium', accentClass)}>
        <Codicon name={icon} size="0.875rem" />
        {label}
      </div>

      <div className="flex flex-col gap-1">
        {paths.length === 0 ? (
          <p className="py-2 text-xs italic text-muted-foreground">{emptyText}</p>
        ) : (
          paths.map((p, i) => (
            <div
              className="flex items-center gap-1.5 rounded-[2.5px] border border-(--ui-stroke-tertiary) bg-(--ui-editor-surface-background) px-2 py-1"
              key={i}
            >
              <Codicon className="shrink-0 text-muted-foreground" name="file-directory" size="0.75rem" />
              <span className="min-w-0 flex-1 truncate font-mono text-[0.6875rem] leading-4">{p}</span>
              <Button
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => onRemove(i)}
                size="micro"
                variant="text"
              >
                <Codicon name="close" size="0.75rem" />
              </Button>
            </div>
          ))
        )}
      </div>

      <div className="flex items-center gap-1">
        <Input
          className="h-7 font-mono text-[0.6875rem]"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {handleAdd()}
          }}
          placeholder="/path/to/dir"
          value={input}
        />
        <Button disabled={!input.trim()} onClick={handleAdd} size="icon-xs" variant="secondary">
          <Codicon name="add" size="0.875rem" />
        </Button>
      </div>
    </div>
  )
}

export function PathEditor({
  allowedPaths,
  forbiddenPaths,
  onChange,
  loading
}: PathEditorProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-6">
      <PathColumn
        accentClass="text-emerald-600"
        emptyText="No paths configured"
        icon="check"
        label="Allowed"
        onAdd={(val) => onChange([...allowedPaths, val], forbiddenPaths)}
        onRemove={(idx) => onChange(allowedPaths.filter((_, i) => i !== idx), forbiddenPaths)}
        paths={allowedPaths}
      />
      <PathColumn
        accentClass="text-red-500"
        emptyText="No paths configured"
        icon="error"
        label="Forbidden"
        onAdd={(val) => onChange(allowedPaths, [...forbiddenPaths, val])}
        onRemove={(idx) => onChange(allowedPaths, forbiddenPaths.filter((_, i) => i !== idx))}
        paths={forbiddenPaths}
      />
    </div>
  )
}
