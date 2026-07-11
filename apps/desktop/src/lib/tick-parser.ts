import { readDesktopDir, readDesktopFileText } from '@/lib/desktop-fs'
import { getLedgerPath } from '@/lib/ledger-reader'

// ── Types ────────────────────────────────────────────────────────────────────

export interface GateCounts {
  T0: number
  T1: number
  T2: number
  T3: number
}

export interface TickReport {
  tick_number: number
  date: string
  budget_spent: number
  workers_active: number
  hypotheses_created: number
  hypotheses_completed: number
  gates_passed: number
  gates: Partial<GateCounts>
  summary_text: string
  raw_markdown: string
}

// ── Parser ───────────────────────────────────────────────────────────────────

/**
 * Parse a single AlphaForge tick report from raw markdown text.
 * Returns a TickReport with best-effort field extraction.
 */
export function parseTickReport(markdown: string): TickReport {
  const report: TickReport = {
    tick_number: 0,
    date: '',
    budget_spent: 0,
    workers_active: 0,
    hypotheses_created: 0,
    hypotheses_completed: 0,
    gates_passed: 0,
    gates: {},
    summary_text: '',
    raw_markdown: markdown,
  }

  try {
    // ## Tick N
    const tickMatch = markdown.match(/^##\s+Tick\s+(\d+)/im)

    if (tickMatch) {
      report.tick_number = parseInt(tickMatch[1], 10)
    }

    // Date line: "Date: YYYY-MM-DD" or similar
    const dateMatch = markdown.match(
      /^Date[:\s]+(\d{4}-\d{2}-\d{2})/im,
    )

    if (dateMatch) {
      report.date = dateMatch[1]
    }

    // Budget spent: "$XXX.XX" near "# Budget" or "Budget spent:" lines
    const budgetMatch = markdown.match(
      /Budget\s+spent[:\s]+\$?([0-9,.]+)/im,
    )

    if (budgetMatch) {
      report.budget_spent = parseNumeric(budgetMatch[1])
    } else {
      const dollarMatch = markdown.match(
        /^\$\s*([0-9,.]+)\s*\/\s*\$?/im,
      )

      if (dollarMatch) {
        report.budget_spent = parseNumeric(dollarMatch[1])
      }
    }

    // Workers: active N
    const workersMatch = markdown.match(
      /Workers?:?\s+active[:\s]+(\d+)/im,
    )

    if (workersMatch) {
      report.workers_active = parseInt(workersMatch[1], 10)
    } else {
      // Count list items under a "## Workers" heading
      const workerSection = markdown.match(
        /^##\s+Workers\s*\n([\s\S]*?)(?=\n##\s|$)/im,
      )

      if (workerSection) {
        const workerItems =
          workerSection[1].match(/^[-*]\s+.+/gm)

        if (workerItems) {
          report.workers_active = workerItems.length
        }
      }
    }

    // Hypotheses created / completed
    const createdMatch = markdown.match(
      /Hypotheses?\s+created[:\s]+(\d+)/im,
    )

    if (createdMatch) {
      report.hypotheses_created = parseInt(createdMatch[1], 10)
    }

    const completedMatch = markdown.match(
      /Hypotheses?\s+completed[:\s]+(\d+)/im,
    )

    if (completedMatch) {
      report.hypotheses_completed = parseInt(completedMatch[1], 10)
    }

    // Gates passed / gate counts
    const gatesPassedMatch = markdown.match(
      /Gates?\s+passed[:\s]+(\d+)/im,
    )

    if (gatesPassedMatch) {
      report.gates_passed = parseInt(gatesPassedMatch[1], 10)
    }

    // Individual gate counts: "T0: 3", "T1: 5", etc.
    for (const gate of ['T0', 'T1', 'T2', 'T3'] as const) {
      const gateMatch = markdown.match(
        new RegExp(`${gate}:\\s+(\\d+)`, 'i'),
      )

      if (gateMatch) {
        report.gates[gate] = parseInt(gateMatch[1], 10)
      }
    }

    // Summary text: first paragraph after "# Summary" or first non-heading
    // paragraph
    const summaryMatch = markdown.match(
      /^#\s+Summary\s*\n([\s\S]*?)(?=\n##?\s|$)/im,
    )

    if (summaryMatch) {
      report.summary_text = summaryMatch[1].trim()
    } else {
      // Fallback: grab the first substantial paragraph
      const paraMatch = markdown.match(
        /^(?!##|#)([A-Z][^#]{20,})/m,
      )

      if (paraMatch) {
        report.summary_text = paraMatch[1].trim()
      }
    }
  } catch {
    // Graceful: return whatever we managed to extract
  }

  return report
}

/**
 * Read the most recent tick report from the configured ledger path.
 * Looks for files matching reports/<date>-tick.md, sorts by date descending,
 * and parses the most recent.
 */
export async function readLatestTickReport(
  ledgerPathOverride?: string,
): Promise<TickReport | null> {
  try {
    const basePath = ledgerPathOverride || getLedgerPath()

    // Normalize ~/
    const home =
      process.env.HOME || process.env.USERPROFILE || '~'

    const resolvedBase = basePath.replace(/^~/, home)

    const reportsPath = `${resolvedBase}/reports`
    const dirResult = await readDesktopDir(reportsPath)

    if (!dirResult || !dirResult.entries) {
      console.warn('[tick-parser] No reports directory found')

      return null
    }

    // Filter for tick markdown files and sort by name descending (date order)
    const tickFiles = dirResult.entries
      .filter(
        (e) =>
          !e.isDirectory &&
          /^\d{4}-\d{2}-\d{2}-tick\.md$/.test(e.name),
      )
      .sort((a, b) => b.name.localeCompare(a.name))

    if (tickFiles.length === 0) {
      console.warn('[tick-parser] No tick report files found')

      return null
    }

    const latest = tickFiles[0]

    const fileResult = await readDesktopFileText(
      `${resolvedBase}/reports/${latest.name}`,
    )

    if (fileResult.binary) {
      console.warn(`[tick-parser] ${latest.name} is binary, skipping`)

      return null
    }

    return parseTickReport(fileResult.text)
  } catch (err) {
    console.warn('[tick-parser] Error reading latest tick report:', err)

    return null
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseNumeric(str: string): number {
  const cleaned = str.replace(/[,$]/g, '')
  const num = parseFloat(cleaned)

  return Number.isNaN(num) ? 0 : num
}
