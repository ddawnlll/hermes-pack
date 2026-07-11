// ── Types ────────────────────────────────────────────────────────────────────

export interface GitHubIssue {
  number: number
  title: string
  state: 'open' | 'closed'
  labels: string[]
  milestone: string | null
  assignee: string | null
  html_url: string
}

export interface GitHubMilestone {
  number: number
  title: string
  state: 'open' | 'closed'
  due_on: string | null
  open_issues: number
  closed_issues: number
}

// ── Configuration ────────────────────────────────────────────────────────────

const GITHUB_API_BASE = 'https://api.github.com'

/**
 * Build headers for GitHub API requests.
 * If the GITHUB_TOKEN env var is set, it's used as a Bearer token for
 * authenticated requests (higher rate limit: 5000 req/hr vs 60 req/hr).
 */
function headers(): Record<string, string> {
  const h: Record<string, string> = {
    Accept: 'application/vnd.github.v3+json',
    'Content-Type': 'application/json',
    'User-Agent': 'Hermes-Desktop-AlphaForge',
  }

  const token = process.env.GITHUB_TOKEN

  if (token) {
    h.Authorization = `Bearer ${token}`
  }

  return h
}

// ── API Methods ──────────────────────────────────────────────────────────────

/**
 * List GitHub issues for a given repo, optionally filtered by milestone.
 *
 * @param repo  Repository in "owner/repo" format (e.g. "nousresearch/hermes-agent")
 * @param milestone  Optional milestone title to filter by
 * @returns Array of GitHubIssue objects (empty on error)
 */
export async function listIssues(
  repo: string,
  milestone?: string,
): Promise<GitHubIssue[]> {
  try {
    const params = new URLSearchParams({
      per_page: '100',
      state: 'all',
    })

    if (milestone) {
      params.set('milestone', milestone)
    }

    const url = `${GITHUB_API_BASE}/repos/${repo}/issues?${params}`
    const response = await fetch(url, { headers: headers() })

    if (!response.ok) {
      console.warn(
        `[github-bridge] listIssues returned ${response.status} for ${repo}`,
      )

      return []
    }

    const data: unknown = await response.json()

    if (!Array.isArray(data)) {
      console.warn(
        '[github-bridge] listIssues response is not an array',
      )

      return []
    }

    return data.map(normalizeIssue)
  } catch (err) {
    console.warn('[github-bridge] listIssues error:', err)

    return []
  }
}

/**
 * List milestones for a given repo.
 *
 * @param repo  Repository in "owner/repo" format (e.g. "nousresearch/hermes-agent")
 * @returns Array of GitHubMilestone objects (empty on error)
 */
export async function listMilestones(
  repo: string,
): Promise<GitHubMilestone[]> {
  try {
    const params = new URLSearchParams({
      per_page: '100',
      state: 'all',
      direction: 'desc',
      sort: 'due_on',
    })

    const url = `${GITHUB_API_BASE}/repos/${repo}/milestones?${params}`
    const response = await fetch(url, { headers: headers() })

    if (!response.ok) {
      console.warn(
        `[github-bridge] listMilestones returned ${response.status} for ${repo}`,
      )

      return []
    }

    const data: unknown = await response.json()

    if (!Array.isArray(data)) {
      console.warn(
        '[github-bridge] listMilestones response is not an array',
      )

      return []
    }

    return data.map(normalizeMilestone)
  } catch (err) {
    console.warn('[github-bridge] listMilestones error:', err)

    return []
  }
}

// ── Normalization ────────────────────────────────────────────────────────────

function normalizeIssue(raw: unknown): GitHubIssue {
  const obj =
    raw && typeof raw === 'object'
      ? (raw as Record<string, unknown>)
      : {}

  return {
    number: Number(obj.number) || 0,
    title: String(obj.title || ''),
    state: normalizeState(obj.state),
    labels: extractLabels(obj.labels),
    milestone: extractMilestoneTitle(obj.milestone),
    assignee: extractAssigneeLogin(obj.assignee),
    html_url: String(obj.html_url || ''),
  }
}

function normalizeMilestone(raw: unknown): GitHubMilestone {
  const obj =
    raw && typeof raw === 'object'
      ? (raw as Record<string, unknown>)
      : {}

  return {
    number: Number(obj.number) || 0,
    title: String(obj.title || ''),
    state: normalizeState(obj.state),
    due_on: obj.due_on ? String(obj.due_on) : null,
    open_issues: Number(obj.open_issues) || 0,
    closed_issues: Number(obj.closed_issues) || 0,
  }
}

// ── Field extractors ─────────────────────────────────────────────────────────

function normalizeState(val: unknown): 'open' | 'closed' {
  if (val === 'open' || val === 'closed') {return val}

  return 'open'
}

function extractLabels(val: unknown): string[] {
  if (!Array.isArray(val)) {return []}

  return val
    .map((l) => {
      if (l && typeof l === 'object') {return String((l as Record<string, unknown>).name || '')}

      return String(l)
    })
    .filter(Boolean)
}

function extractMilestoneTitle(val: unknown): string | null {
  if (!val || typeof val !== 'object') {return null}

  return String((val as Record<string, unknown>).title || '') || null
}

function extractAssigneeLogin(val: unknown): string | null {
  if (!val || typeof val !== 'object') {return null}

  return String((val as Record<string, unknown>).login || '') || null
}
