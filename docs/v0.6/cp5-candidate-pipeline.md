# Candidate Pipeline View (CP-5)

**Issue:** #93 (Track C)
**Gates:** operatör görünürlüğü

## Contract

Cockpit'te **candidate pipeline view**: tüm aktif candidate'lar state'lerine göre gruplanmış, geçişler canlı izlenir.

## Görünüm

- **Sütun layout**: state'e göre sütunlar (DRAFT, EVALUATING, REBASE_REQUIRED, QUEUED, PROMOTING, PROMOTED, ROLLED_BACK, FAILED, DEAD)
- **Card**: candidate_id, asset_type, effect_class, age in ticks, current cost
- **Drag-to-rebase**: REBASE_REQUIRED kolonundaki card'ı "manual rebase"a al (human escalation)
- **Detail drawer**: full state history + rollback pointer + precedents

## API

```typescript
export interface CandidateCard {
  id: string;
  state: "DRAFT" | "EVALUATING" | "REBASE_REQUIRED" | "QUEUED" | "PROMOTING" | "PROMOTED" | "ROLLED_BACK" | "FAILED" | "DEAD";
  asset_type: "code" | "config" | "db" | "belief";
  effect_class: "reversible_internal" | "compensable_external" | "irreversible_external";
  age_ticks: number;
  cost: number;
  base_state_hash: string;
  rollback_pointer?: { storage: string; key: string };
}
```

## Data source (fazlar)

- **Faz 1 (mock)**: `apps/desktop/mission-control/lib/mockCandidates.ts` — 10 örnek
- **Faz 2 (gerçek)**: `apps/desktop/mission-control/lib/candidateSource.ts` — BE-1 #82 + DL-2 #97'den beslenir

## Acceptance criteria

- [ ] `apps/desktop/mission-control/components/CandidatePipeline/` (yeni)
- [ ] Mock data source (Faz 1)
- [ ] Sütun layout + card + detail drawer
- [ ] Drag-to-rebase action
- [ ] Real-time update (CP-6 #94)
- [ ] Unit testler: state machine UI mapping
