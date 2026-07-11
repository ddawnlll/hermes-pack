# Delta-first Pulse View (CP-1)

**Issue:** #89 (Track C, Cockpit)
**Status:** Accepted — v0.6
**Consumed by:** apps/desktop/mission-control/components/DeltaPulse/ (new)
**Completion gates:** #6 (Cockpit delta)
**Why:** The AFK dönemi sonunda cockpit'i açan kişi 5 saniyede ne olduğunu anlamalı. Bu doc, bileşenin tasarım prensiplerini ve sözleşmesini belirler. Implementation ayrı bir PR'da gelecektir.

## 1. What this contract locks

`apps/desktop/mission-control/components/DeltaPulse/` — bir React component. Her tick başına tüm olayların özeti yerine, **sadece değişenler** gösterilir. AFK dönemi sonunda cockpit'i açan kişi 5 saniyede ne olduğunu anlamalı.

## 2. Tasarım prensipleri

- **Snapshot → delta**: önceki tick'ten bu tick'e ne değişti.
- **Categorization**: yeni candidate, transitioned candidate, failed rollback, kill, pause.
- **3 satırda özet**: tick header (3 metrik: promoted, rolled_back, killed) + 1-2 önemli delta + "show more" expansion.

## 3. API sözleşmesi

```typescript
// apps/desktop/mission-control/hooks/useDeltaPulse.ts
export interface DeltaPulseTick {
  tick_id: number;
  promoted: number;
  rolled_back: number;
  killed: number;
  deltas: DeltaPulseDelta[];
  "all_quiet": boolean;
}

export type DeltaPulseDelta =
  | { kind: "new_candidate"; candidate_id: string; asset_type: string; effect_class: string }
  | { kind: "transitioned"; candidate_id: string; from: string; to: string }
  | { kind: "failed_rollback"; candidate_id: string; reason: string }
  | { kind: "kill"; candidate_id?: string; reason: string }
  | { kind: "pause"; candidate_id?: string; reason: string }
  | { kind: "shadow_fail"; candidate_id: string; reason: string }
  | { kind: "canary_fail"; candidate_id: string; reason: string };

export function useDeltaPulse(opts?: { sinceTickId?: number }): {
  current: DeltaPulseTick | null;
  isLoading: boolean;
  error: Error | null;
  lastSeenTickId: number | null;
};
```

## 4. Veri kaynağı

- **Phase 1 (mock)**: `apps/desktop/mission-control/lib/mockDeltas.ts` — 10 örnek delta tick'i.
- **Phase 2 (gerçek)**: `apps/desktop/mission-control/lib/deltaSource.ts` — `events.jsonl`'i (CP-6 #94 üzerinden) dinler, delta hesaplar.

`deltaSource.ts`, `tick-journal.py`'yi (BE-6 #84 precedent memory) consume eder. Her event'i delta'ya dönüştürür.

## 5. Acceptance criteria

- [ ] `apps/desktop/mission-control/components/DeltaPulse/` (yeni component, mock data ile çalışır)
- [ ] `apps/desktop/mission-control/hooks/useDeltaPulse.ts` — delta computation hook
- [ ] Mock data source: 10 örnek tick (boş, tek değişiklik, çok değişiklik)
- [ ] Tick header: 3 metrik tile (Promoted / Rolled Back / Killed) + delta badge
- [ ] "Last seen" timestamp ile kullanıcının kaç tick kaçırdığını göster
- [ ] Accessibility: screen reader için delta list semantic
- [ ] Unit testler: delta computation (boş, tek değişiklik, çok değişiklik)
- [ ] Visual regression test: delta olmayan tick = "all quiet" state gösterir (boş ekran değil)
- [ ] CP-4 (online↔AFK handoff) ile entegre: AFK → Online dönüşte ilk pulse "catch up" rolu oynar

## 6. Consumed by

- **CP-1** (#89): bu doc.
- **CP-4** (#92): online↔AFK handoff — "catch up" rolu.
- **CP-2** (#90): attention budget queue — pulse'taki kritik item'lar queue'ya yansır.
- **CP-6** (#94): local realtime adapter — event stream kaynağı.

## 7. Reference

- A-4 (#79): State-of-Record cutover — delta'lar file veya DB'den beslenebilir.
- A-2 (#77): Workspace Intent — `human_override` olayları pulse'ta gösterilir.
- BE-7 (#88): golden replay — senaryolardan biri delta pulse'ın doğru render ettiğini kanıtlar.

---

**Note**: Bu doc, CP-1 component implementation PR'ı tarafından consume edilecek. Component dosyaları (`DeltaPulse.tsx`, `useDeltaPulse.ts`, vb.) ayrı bir implementation PR'da gelecektir. Bu PR, sözleşmeyi ve acceptance criteria'ları belirler; gerçek TypeScript kodu implementation PR'ında yazılır.
