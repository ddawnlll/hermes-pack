import { readDesktopFileText, writeDesktopFileText } from '@/lib/desktop-fs'

// ── Types ────────────────────────────────────────────────────────────────────

export interface ControlConfig {
  mode: 'auto' | 'manual' | 'paused'
  budget_usd: number
  parallel_workers: number
  human_instruction: string
  allowed_paths: string[]
  forbidden_paths: string[]
}

export interface GateCounts {
  T0: number
  T1: number
  T2: number
  T3: number
}

export interface OrchestratorState {
  current_tick: number
  total_budget_spent: number
  worker_status: Record<string, WorkerStatus>
  gates: GateCounts
  last_updated: string | null
}

export type WorkerStatus = 'running' | 'idle' | 'failed' | 'completed'

export interface HypothesisDoc {
  id: string
  title: string
  status: string
  created_at: string
  updated_at: string
  content: string
}

// ── State ────────────────────────────────────────────────────────────────────

// Ledger path: prefer VITE_LEDGER_PATH env var, fall back to default.
// Set VITE_LEDGER_PATH in apps/desktop/.env or via Control Plane.
let ledgerBasePath: string =
  (typeof window !== 'undefined' && (window as any).__ENV__?.VITE_LEDGER_PATH) ||
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_LEDGER_PATH) ||
  '~/.hermes/alphaforge'

/** Set the ledger base path (e.g. for testing or custom installs). */
export function setLedgerPath(path: string): void {
  ledgerBasePath = path
}

/** Get the current ledger base path. */
export function getLedgerPath(): string {
  return ledgerBasePath
}

/** Expand a leading ~/ to the user's home directory. */
function expandHome(p: string): string {
  if (p.startsWith('~/') || p === '~') {
    const home = process.env.HOME || process.env.USERPROFILE || '~'

    return p.replace(/^~/, home)
  }

  return p
}

/** Build a fully qualified path relative to the ledger base. */
function ledgerPath(relative: string): string {
  return `${expandHome(ledgerBasePath)}/${relative}`
}

// ── Simple YAML parser (regex-based, no external deps) ───────────────────────

/**
 * Parse a YAML string that uses top-level scalar keys (strings, numbers,
 * booleans, arrays of strings) — enough for control.yaml and hypothesis files.
 * Returns null on parse failure.
 */
function parseSimpleYaml(text: string): Record<string, unknown> | null {
  try {
    const result: Record<string, unknown> = {}
    const lines = text.split('\n')

    for (const raw of lines) {
      const line = raw.replace(/#.*$/, '').trim()

      if (!line) {continue}

      // Match key: value patterns
      const match = line.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$/)

      if (!match) {continue}

      const key = match[1]
      let value: unknown = match[2].trim()

      // Quoted string
      if (
        (value as string).startsWith("'") &&
        (value as string).endsWith("'")
      ) {
        value = (value as string).slice(1, -1)
      } else if (
        (value as string).startsWith('"') &&
        (value as string).endsWith('"')
      ) {
        value = (value as string).slice(1, -1)
      } else if ((value as string) === 'true') {
        value = true
      } else if ((value as string) === 'false') {
        value = false
      } else if ((value as string) === 'null' || (value as string) === '~') {
        value = null
      } else if (/^-?\d+\.?\d*$/.test(value as string)) {
        const num = Number(value)

        if (!Number.isNaN(num)) {value = num}
      } else if ((value as string).startsWith('[') && (value as string).endsWith(']')) {
        // Simple array of strings
        const inner = (value as string).slice(1, -1).trim()
        value = inner
          ? inner.split(',').map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
          : []
      }

      result[key] = value
    }

    return result
  } catch {
    return null
  }
}

// ── Readers ──────────────────────────────────────────────────────────────────

/**
 * Read and parse control.yaml from the ledger directory.
 * Returns null when the file does not exist (ENOENT).
 * Throws on parse failures.
 */
export async function readControlYaml(): Promise<ControlConfig | null> {
  try {
    const result = await readDesktopFileText(ledgerPath('control.yaml'))

    if (result.binary) {
      console.warn('[ledger-reader] control.yaml is binary, skipping')

      return null
    }

    const parsed = parseSimpleYaml(result.text)

    if (!parsed) {
      throw new Error('Failed to parse control.yaml')
    }

    return {
      mode: parseMode(parsed.mode),
      budget_usd: Number(parsed.budget_usd) || 0,
      parallel_workers: Number(parsed.parallel_workers) || 1,
      human_instruction: String(parsed.human_instruction || ''),
      allowed_paths: asStringArray(parsed.allowed_paths),
      forbidden_paths: asStringArray(parsed.forbidden_paths),
    }
  } catch (err: unknown) {
    if (isNodeError(err) && err.code === 'ENOENT') {
      return null
    }

    console.warn('[ledger-reader] Error reading control.yaml:', err)
    throw err
  }
}

/**
 * Read and parse state.json from the ledger directory.
 * Returns null when the file does not exist or on any error (graceful).
 */
export async function readStateJson(): Promise<OrchestratorState | null> {
  try {
    const result = await readDesktopFileText(ledgerPath('state.json'))

    if (result.binary) {
      console.warn('[ledger-reader] state.json is binary, skipping')

      return null
    }

    const data = JSON.parse(result.text) as Record<string, unknown>

    return {
      current_tick: Number(data.current_tick) || 0,
      total_budget_spent: Number(data.total_budget_spent) || 0,
      worker_status: parseWorkerStatus(data.worker_status),
      gates: {
        T0: Number((data.gates as Record<string, unknown>)?.['T0']) || 0,
        T1: Number((data.gates as Record<string, unknown>)?.['T1']) || 0,
        T2: Number((data.gates as Record<string, unknown>)?.['T2']) || 0,
        T3: Number((data.gates as Record<string, unknown>)?.['T3']) || 0,
      },
      last_updated: data.last_updated
        ? String(data.last_updated)
        : null,
    }
  } catch (err: unknown) {
    if (isNodeError(err) && err.code === 'ENOENT') {
      return null
    }

    console.warn('[ledger-reader] Error reading state.json:', err)

    return null
  }
}

/**
 * Read and parse a single hypothesis YAML document by id.
 * The file is expected at hypothesis/<id>.yaml.
 * Returns null when the file does not exist.
 * Throws on parse failures.
 */
export async function readHypothesis(id: string): Promise<HypothesisDoc | null> {
  try {
    const result = await readDesktopFileText(
      ledgerPath(`hypothesis/${id}.yaml`),
    )

    if (result.binary) {
      console.warn(`[ledger-reader] hypothesis/${id}.yaml is binary, skipping`)

      return null
    }

    const parsed = parseSimpleYaml(result.text)

    if (!parsed) {
      throw new Error(`Failed to parse hypothesis/${id}.yaml`)
    }

    return {
      id: String(parsed.id || id),
      title: String(parsed.title || ''),
      status: String(parsed.status || 'draft'),
      created_at: String(parsed.created_at || ''),
      updated_at: String(parsed.updated_at || ''),
      content: String(parsed.content || ''),
    }
  } catch (err: unknown) {
    if (isNodeError(err) && err.code === 'ENOENT') {
      return null
    }

    console.warn(`[ledger-reader] Error reading hypothesis/${id}.yaml:`, err)
    throw err
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseMode(
  val: unknown,
): 'auto' | 'manual' | 'paused' {
  if (val === 'auto' || val === 'manual' || val === 'paused') {return val}

  return 'manual'
}

function parseWorkerStatus(
  val: unknown,
): Record<string, WorkerStatus> {
  if (!val || typeof val !== 'object') {return {}}
  const raw = val as Record<string, unknown>
  const out: Record<string, WorkerStatus> = {}

  for (const [k, v] of Object.entries(raw)) {
    if (
      v === 'running' ||
      v === 'idle' ||
      v === 'failed' ||
      v === 'completed'
    ) {
      out[k] = v
    }
  }

  return out
}

function asStringArray(val: unknown): string[] {
  if (Array.isArray(val)) {return val.map(String)}

  return []
}

interface NodeError extends Error {
  code?: string
}

function isNodeError(err: unknown): err is NodeError {
  return err instanceof Error && 'code' in err
}

// ── Writers ─────────────────────────────────────────────────────────────────

/**
 * Serialize ControlConfig to YAML and write control.yaml to the ledger directory.
 */
export async function writeControlYaml(config: ControlConfig): Promise<void> {
  const lines = [
    `mode: ${config.mode}`,
    `budget_usd: ${config.budget_usd}`,
    `parallel_workers: ${config.parallel_workers}`,
    `human_instruction: "${(config.human_instruction || '').replace(/"/g, '\\"')}"`,
    `allowed_paths:`,
    ...config.allowed_paths.map(p => `  - "${p}"`),
    `forbidden_paths:`,
    ...config.forbidden_paths.map(p => `  - "${p}"`),
  ]
  await writeDesktopFileText(ledgerPath('control.yaml'), lines.join('\n'))
}
