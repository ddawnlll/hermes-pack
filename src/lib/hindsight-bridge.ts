// ── Types ────────────────────────────────────────────────────────────────────

export interface RecallResult {
  id: string
  content: string
  score: number
  timestamp: string
  tags: string[]
}

// ── Configuration ────────────────────────────────────────────────────────────

const DEFAULT_HINDSIGHT_URL = 'http://localhost:9885'

const HINDSIGHT_BANK = process.env.HINDSIGHT_BANK_ID || 'hermes'

let hindsightUrl: string = DEFAULT_HINDSIGHT_URL

/** Override the Hindsight API base URL. */
export function setHindsightUrl(url: string): void {
  hindsightUrl = url
}

/** Get the current Hindsight API base URL. */
export function getHindsightUrl(): string {
  return hindsightUrl
}

// ── API Methods ──────────────────────────────────────────────────────────────

/**
 * Recall past memories matching the query string.
 * Calls POST /v1/default/banks/{bank}/memories/recall on the Hindsight REST API.
 */
export async function recall(
  query: string,
): Promise<RecallResult[]> {
  try {
    const url = `${hindsightUrl}/v1/default/banks/${HINDSIGHT_BANK}/memories/recall`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    })

    if (!response.ok) {
      console.warn(`[hindsight-bridge] recall returned ${response.status}`)
      return []
    }

    const data: unknown = await response.json()

    if (!Array.isArray(data)) {
      console.warn('[hindsight-bridge] recall response is not an array')
      return []
    }

    return data.map(normalizeRecallResult)
  } catch (err) {
    console.warn('[hindsight-bridge] recall error:', err)
    return []
  }
}

/**
 * Ask the Hindsight memory system a reflective question.
 * Calls POST /v1/default/banks/{bank}/reflect on the Hindsight REST API.
 */
export async function reflect(
  question: string,
): Promise<string | null> {
  try {
    const url = `${hindsightUrl}/v1/default/banks/${HINDSIGHT_BANK}/reflect`
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question }),
    })

    if (!response.ok) {
      console.warn(`[hindsight-bridge] reflect returned ${response.status}`)
      return null
    }

    const data: unknown = await response.json()

    if (typeof data === 'string') return data

    if (data && typeof data === 'object') {
      const obj = data as Record<string, unknown>
      if (typeof obj.answer === 'string') return obj.answer
      if (typeof obj.result === 'string') return obj.result
      if (typeof obj.reflection === 'string') return obj.reflection
    }

    return String(data)
  } catch (err) {
    console.warn('[hindsight-bridge] reflect error:', err)
    return null
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function normalizeRecallResult(raw: unknown): RecallResult {
  const obj = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}

  return {
    id: String(obj.id || ''),
    content: String(obj.content || obj.text || ''),
    score: typeof obj.score === 'number' ? obj.score : 0,
    timestamp: String(obj.timestamp || obj.created_at || ''),
    tags: asStringArray(obj.tags),
  }
}

function asStringArray(val: unknown): string[] {
  if (Array.isArray(val)) {return val.map(String)}

  return []
}
