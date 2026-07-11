# Attention Budget Queue (CP-2)

**Issue:** #90 (Track C, Cockpit)
**Status:** Accepted — v0.6
**Consumed by:** apps/desktop/mission-control/components/AttentionQueue/ (new)
**Completion gates:** indirectly contributes to #6 (Cockpit delta) — critical items surface here.
**Why:** Information overload'ı önlemek, kritik olanı ön plana çıkarmak. Bu doc, kuyruğun sözleşmesini ve öncelik kurallarını belirler. Implementation ayrı bir PR'da gelecektir.

## 1. What this contract locks

`apps/desktop/mission-control/components/AttentionQueue/` — bir React component. Aynı anda max **3 bildirim/action** görünür. Daha fazlası **queue**'da birikir, kullanıcı "show all" ile erişir.

## 2. Queue mantığı

- **Priority-based**: `kill > irreversible_external > reversible candidate > routine update`
- **Auto-dismiss**: routine update 30s sonra kaybolur
- **Persistent**: kill ve pause action'ları kapatılamaz (sadece "acknowledged" işaretlenir)
- **3 max**: ekranda 3'ten fazla active item varsa en düşük priority fade out olur

## 3. API sözleşmesi

```typescript
// apps/desktop/mission-control/hooks/useAttentionBudget.ts
export type AttentionPriority = "critical" | "high" | "medium" | "low" | "routine";

export interface AttentionItem {
  id: string;
  priority: AttentionPriority;
  kind: "kill" | "pause" | "rollback" | "candidate_proposed" | "candidate_promoted" | "info";
  title: string;
  body?: string;
  candidate_id?: string;
  created_at: string; // ISO-8601
  auto_dismiss_at?: string; // ISO-8601; set iff priority == "routine"
  requires_acknowledgment: boolean;
}

export interface AttentionQueueState {
  visible: AttentionItem[]; // length <= 3
  queued: AttentionItem[];   // length unbounded
  total: number;             // visible.length + queued.length
}

export interface AttentionBudget {
  push(item: AttentionItem): void;
  acknowledge(id: string): void;
  showAll(): AttentionItem[]; // returns all queued items
  state: AttentionQueueState;
}
```

## 4. Priority kuralları (kaynak: AFK autonomy)

| Priority | Trigger | Auto-dismiss | Ack required |
|---|---|---|---|
| `critical` | `kill` action issued, `pause` issued by system | no | yes |
| `high` | `irreversible_external` candidate, `rollback` failed | no | yes |
| `medium` | Reversible candidate promoted/failed, budget exceeded (GA-2) | no | no |
| `low` | T4 disposition recommendation | yes (10s) | no |
| `routine` | Tick header, system info | yes (30s) | no |

## 5. Consumed by

- **CP-1** (#89): delta pulse'taki kritik item'lar queue'ya yansır.
- **CP-3** (#91): intervention grammar — queue item'ları intervention action'larına dönüşebilir.
- **CP-4** (#92): online↔AFK handoff — "catch up" sırasında queue sıfırlanır.
- **GA-1** (#99): AFK autonomy — AFK sırasında queue 0 (otonom); AFK bittiğinde tüm queue item'ları gösterilir.

## 6. Acceptance criteria

- [ ] `apps/desktop/mission-control/components/AttentionQueue/` (yeni)
- [ ] `apps/desktop/mission-control/hooks/useAttentionBudget.ts` — budget manager
- [ ] Priority tanımları: `critical | high | medium | low | routine`
- [ ] 3 max visible, geri kalan collapsed
- [ ] Auto-dismiss timer (routine için 30s, low için 10s, diğerleri persistent)
- [ ] Keyboard shortcut: `Cmd+]` ile queue toggle
- [ ] Accessibility: focus management (queue collapse/expand sırasında focus trap)
- [ ] Unit testler: priority order, max-3 enforcement, auto-dismiss
- [ ] Integration test: critical item > 3 routine items → critical visible, routine collapsed

## 7. Reference

- A-1 (#76): Effect Taxonomy — `irreversible_external` otomatik high priority.
- A-4 (#79): State-of-Record — kill/pause queue'da critical olarak görünür.
- GA-1 (#99): AFK autonomy — AFK sırasında queue suppressed.

---

**Note**: Bu doc, CP-2 component implementation PR'ı tarafından consume edilecek. Component dosyaları (`AttentionQueue.tsx`, `useAttentionBudget.ts`, vb.) ayrı bir implementation PR'da gelecektir. Bu PR, sözleşmeyi ve acceptance criteria'ları belirler.
