/**
 * RemoteBridge — AlphaForge ledger access via Gateway API + local fallback
 *
 * When SSH tunnel is active (bash deploy/tunnel.sh), connects to the remote
 * Gateway API (localhost:8530) for all ledger operations.
 * Falls back to local desktop-fs when offline.
 */

import { readDesktopFileText, writeDesktopFileText, isDesktopFsRemoteMode } from '@/lib/desktop-fs'
import { getLedgerPath, setLedgerPath } from '@/lib/ledger-reader'

// ── Types ────────────────────────────────────────────────────────────────────

export interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  size: number
  modifiedAt: string
}

export interface GatewayStatus {
  pid: number
  version: string
  uptime: string
}

// ── Configuration ────────────────────────────────────────────────────────────

const DEFAULT_GATEWAY_URL = 'http://localhost:8530'
const DEFAULT_HINDSIGHT_URL = 'http://localhost:9885'

let gatewayUrl: string = process.env.GATEWAY_URL || DEFAULT_GATEWAY_URL
let hindsightUrl: string = process.env.REMOTE_HINDSIGHT_URL || DEFAULT_HINDSIGHT_URL

export function setGatewayUrl(url: string) { gatewayUrl = url }
export function setHindsightUrl(url: string) { hindsightUrl = url }

// ── RemoteBridge ─────────────────────────────────────────────────────────────

export class RemoteBridge {
  private _connected = false

  /**
   * Connect to the remote server via SSH tunnel.
   * Requires `bash deploy/tunnel.sh` running in another terminal.
   * Validates by pinging the Gateway health endpoint.
   */
  async connect(): Promise<void> {
    if (this._connected) return

    if (!isDesktopFsRemoteMode()) {
      // Local mode — no-op
      this._connected = true
      return
    }

    // Remote mode: ping Gateway
    try {
      const res = await fetch(`${gatewayUrl}/health`, { signal: AbortSignal.timeout(5000) })
      if (!res.ok) throw new Error(`Gateway returned ${res.status}`)
      const data: GatewayStatus = await res.json()
      console.info(`[RemoteBridge] Connected to Gateway PID ${data.pid}`)
      this._connected = true
    } catch (err) {
      console.warn('[RemoteBridge] Cannot reach Gateway. Is SSH tunnel running?', err)
      throw new Error(
        'Cannot connect to remote Gateway. Start tunnel:\n  bash deploy/tunnel.sh',
      )
    }
  }

  isConnected(): boolean { return this._connected }

  disconnect(): void { this._connected = false }

  // ── File Operations ────────────────────────────────────────────────────

  /** Read a file from the ledger (local or remote via Gateway) */
  async readFile(relativePath: string): Promise<string | null> {
    this.ensureConnected()
    const fullPath = `${getLedgerPath()}/${relativePath}`
    try {
      const result = await readDesktopFileText(fullPath)
      if (result.binary) return null
      return result.text
    } catch {
      return null
    }
  }

  /** Check if a file exists */
  async exists(relativePath: string): Promise<boolean> {
    const content = await this.readFile(relativePath)
    return content !== null
  }

  /** Write a file to the ledger (only in local mode) */
  async writeFile(relativePath: string, content: string): Promise<void> {
    this.ensureConnected()
    const fullPath = `${getLedgerPath()}/${relativePath}`
    await writeDesktopFileText(fullPath, content)
  }

  // ── Gateway API ───────────────────────────────────────────────────────

  /** Ping the Gateway health endpoint */
  async health(): Promise<GatewayStatus> {
    const res = await fetch(`${gatewayUrl}/health`)
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
    return res.json()
  }

  /** Call Gateway RPC method */
  async rpc(method: string, params?: unknown): Promise<unknown> {
    const res = await fetch(`${gatewayUrl}/rpc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params: params || {} }),
    })
    if (!res.ok) throw new Error(`Gateway RPC error: ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(`RPC error: ${data.error.message || JSON.stringify(data.error)}`)
    return data.result
  }

  // ── Hindsight API ──────────────────────────────────────────────────────

  /** Recall memories from Hindsight */
  async recall(query: string): Promise<Array<{ id: string; content: string; score: number }>> {
    try {
      const res = await fetch(`${hindsightUrl}/recall?q=${encodeURIComponent(query)}`)
      if (!res.ok) return []
      return await res.json()
    } catch { return [] }
  }

  /** Reflect via Hindsight */
  async reflect(question: string): Promise<string | null> {
    try {
      const res = await fetch(`${hindsightUrl}/reflect?q=${encodeURIComponent(question)}`)
      if (!res.ok) return null
      return (await res.json()).answer || null
    } catch { return null }
  }

  // ── High-Level ─────────────────────────────────────────────────────────

  /** Get control.yaml mode */
  async getMode(): Promise<string> {
    const content = await this.readFile('control.yaml')
    if (!content) return 'unknown'
    const m = content.match(/^mode:\s*(\S+)/m)
    return m ? m[1] : 'unknown'
  }

  /** Get state.json */
  async getState(): Promise<Record<string, unknown>> {
    const content = await this.readFile('state.json')
    if (!content) return {}
    try { return JSON.parse(content) }
    catch { return {} }
  }

  /** Get list of hypotheses */
  async listHypotheses(): Promise<string[]> {
    const dir = await this.readFile('hypotheses')
    if (!dir) return []
    // Parse the directory listing
    return dir.split('\n').filter(l => l.endsWith('.yaml'))
  }

  // ── Private Helpers ────────────────────────────────────────────────────

  private ensureConnected(): void {
    if (!this._connected) {
      throw new Error('RemoteBridge: call connect() first')
    }
  }
}

// ── Singleton ────────────────────────────────────────────────────────────────

export const bridge = new RemoteBridge()
