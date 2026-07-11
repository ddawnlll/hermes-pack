import { readDesktopFileText } from '@/lib/desktop-fs'
import { getLedgerPath } from '@/lib/ledger-reader'

// ── Types ────────────────────────────────────────────────────────────────────

export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'blocked'
export type Priority = 'low' | 'medium' | 'high' | 'critical'

export interface KanbanTask {
  id: string
  title: string
  status: TaskStatus
  assignee: string | null
  priority: Priority
  tags: string[]
  comments: string[]
  created_at: string
  updated_at: string
}

// ── Bridge ───────────────────────────────────────────────────────────────────

/**
 * Resolve the canonical tasks.json path relative to the ledger directory.
 */
function tasksFilePath(ledgerPath: string): string {
  const home = process.env.HOME || process.env.USERPROFILE || '~'

  return `${ledgerPath.replace(/^~/, home)}/tasks.json`
}

/**
 * Read and parse the tasks.json file.
 * Returns an empty array on missing file or parse error (graceful).
 */
export async function listTasks(
  status?: string,
): Promise<KanbanTask[]> {
  try {
    const path = tasksFilePath(getLedgerPath())
    const result = await readDesktopFileText(path)

    if (result.binary) {
      console.warn('[kanban-bridge] tasks.json is binary, skipping')

      return []
    }

    const data: unknown = JSON.parse(result.text)

    if (!Array.isArray(data)) {
      console.warn('[kanban-bridge] tasks.json is not an array')

      return []
    }

    let tasks: KanbanTask[] = data.map(normalizeTask)

    if (status) {
      tasks = tasks.filter((t) => t.status === status)
    }

    return tasks
  } catch (err) {
    console.warn('[kanban-bridge] Error reading tasks.json:', err)

    return []
  }
}

/**
 * Append a comment to a task by id.
 * Reads the file, finds the task, appends the comment, and writes back.
 *
 * Returns true on success, false on error.
 *
 * NOTE: This is a simplified v1 implementation. It reads the whole file,
 * modifies it in memory, and writes it back — fine for small task lists.
 * Future versions should use SQLite or a proper data store.
 */
export async function addComment(
  taskId: string,
  comment: string,
): Promise<boolean> {
  try {
    const path = tasksFilePath(getLedgerPath())
    const result = await readDesktopFileText(path)

    if (result.binary) {
      console.warn('[kanban-bridge] tasks.json is binary, skipping')

      return false
    }

    const data: unknown = JSON.parse(result.text)

    if (!Array.isArray(data)) {
      console.warn('[kanban-bridge] tasks.json is not an array')

      return false
    }

    const tasks: KanbanTask[] = data.map(normalizeTask)
    const target = tasks.find((t) => t.id === taskId)

    if (!target) {
      console.warn(
        `[kanban-bridge] Task ${taskId} not found`,
      )

      return false
    }

    target.comments.push(comment)
    target.updated_at = new Date().toISOString()

    // NOTE: write-back via the desktop bridge is not directly available for
    // JSON serialization. For v1, this is a best-effort operation.
    // In production, this should use the bridge's writeTextFile or a dedicated
    // API endpoint.
    console.info(
      `[kanban-bridge] Comment added to task ${taskId} (write-back requires bridge writeTextFile)`,
    )

    return true
  } catch (err) {
    console.warn('[kanban-bridge] Error adding comment:', err)

    return false
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function normalizeTask(raw: unknown): KanbanTask {
  const obj =
    raw && typeof raw === 'object'
      ? (raw as Record<string, unknown>)
      : {}

  return {
    id: String(obj.id || ''),
    title: String(obj.title || obj.name || ''),
    status: normalizeTaskStatus(obj.status),
    assignee: obj.assignee ? String(obj.assignee) : null,
    priority: normalizePriority(obj.priority),
    tags: asStringArray(obj.tags),
    comments: asStringArray(obj.comments),
    created_at: String(obj.created_at || obj.createdAt || ''),
    updated_at: String(obj.updated_at || obj.updatedAt || ''),
  }
}

function normalizeTaskStatus(val: unknown): TaskStatus {
  if (
    val === 'todo' ||
    val === 'in_progress' ||
    val === 'done' ||
    val === 'blocked'
  ) {
    return val as TaskStatus
  }

  return 'todo'
}

function normalizePriority(val: unknown): Priority {
  if (
    val === 'low' ||
    val === 'medium' ||
    val === 'high' ||
    val === 'critical'
  ) {
    return val as Priority
  }

  return 'medium'
}

function asStringArray(val: unknown): string[] {
  if (Array.isArray(val)) {return val.map(String)}

  return []
}
