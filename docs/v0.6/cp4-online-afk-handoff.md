# Online↔AFK Handoff (CP-4)

**Issue:** #92 (Track C)
**Gates:** #6 (Cockpit delta, kısmen)

## Contract

Online → AFK ve AFK → Online geçişlerinde cockpit state'inin **snapshot + reconciliation** ekranı.

## Online → AFK

- Kullanıcı "go AFK" der
- Cockpit state'inin son snapshot'ı alınır (DB veya events.jsonl)
- A-4 cutover sırasında her iki yüzeyden de okunur, reconcile, fark varsa gösterilir
- "AFK moduna gir" onayı, tüm pending intervention'lar flush olur

## AFK → Online

- Kullanıcı döner
- AFK süresince olan tüm event'ler replay (CP-1 #89 delta pulse)
- Reconciliation screen:
  - Kaç tick geçti
  - Kaç candidate promoted / rolled_back / killed
  - Hangi human override'lar shadowed (A-2 öncelik kuralı)
  - Bekleyen kararlar (insan escalation gereken)
- Seçenekler: Resume / Stay AFK / Manual review

## API

```typescript
export interface HandoffSnapshot {
  snapshot_id: string;
  taken_at: string;
  mode_before: "online" | "afk";
  state: {
    current_tick: number;
    pending_interventions: number;
    budget_state: { spent: number; remaining: number };
  };
  afk_session?: {
    started_at: string;
    ended_at: string;
    tick_range: [number, number];
    promoted: number;
    rolled_back: number;
    killed: number;
    shadowed_overrides: string[];
  };
}
```

## Acceptance criteria

- [ ] `apps/desktop/mission-control/components/HandoffScreen/` (yeni)
- [ ] `apps/desktop/mission-control/lib/snapshot.ts`
- [ ] Reconciliation logic: events.jsonl → delta → kategori
- [ ] Shadowed override'lar (A-2) reconcile ekranında
- [ ] "Resume" / "Stay AFK" / "Manual review"
- [ ] Unit + E2E test
