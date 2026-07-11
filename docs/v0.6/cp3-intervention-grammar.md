# Intervention Grammar Wiring (CP-3)

**Issue:** #91 (Track C)
**Consumed by:** apps/desktop/mission-control/lib/intent-client.ts
**Gates:** #10 (Human override next tick), kısmen #11 (Shared workspace)

## Contract

Cockpit'ten gelen intervention'lar (PIN, MARK_SUSPECT, ADD_WHISPER, PAUSE, FREEZE, KILL) typed intent'e dönüşür ve Orchestrator'ın intent queue'suna gider (A-2 #77).

## Wiring

1. Cockpit UI action → `intent-client.ts` typed intent (A-2 şemasına uygun)
2. Intent → CP-6 local realtime adapter (#94) üzerinden Orchestrator'a
3. Orchestrator intent'i queue'ya alır, sırayla uygular
4. Uygulama sonucu Cockpit'e geri döner (delta pulse, CP-1 #89)

## Typed intent (from A-2)

```typescript
export type IntentKind = "PIN" | "EVICT" | "MARK_SUSPECT" | "ADD_WHISPER" | "UNMARK_SUSPECT" | "PAUSE" | "FREEZE" | "KILL";

export interface TypedIntent {
  intent_id: string;
  tick_id: number;
  actor: "human" | "t4" | "reflector";
  priority: 0 | 1 | 2;
  operation: IntentKind;
  target: string;
  evidence?: string;
  timestamp: string;
}
```

## API (intent-client.ts)

```typescript
export interface IntentClient {
  send(intent: Omit<TypedIntent, "intent_id" | "timestamp">): Promise<{ intent_id: string; applied: boolean; shadowed_by?: string }>;
  listPending(): Promise<TypedIntent[]>;
}
```

## Acceptance criteria

- [ ] `apps/desktop/mission-control/lib/intent-client.ts` — typed intent client
- [ ] Her intervention tipi için UI action
- [ ] A-2 şemasına uygun payload
- [ ] Optimistic UI: queued → applied | shadowed
- [ ] 5s ack timeout → "pending" göster
- [ ] Unit testler: her intent tipi

## Reference

- A-2 #77 (Workspace Intent) — payload şeması
- A-1 #76 (Effect Taxonomy) — KILL/PARK semantics
- CP-1 #89 (Delta pulse) — UI feedback
- CP-6 #94 (Local realtime) — transport
