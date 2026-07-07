DesignForge draft creation tick.

Workdir is the designforge repo root.

## Your Job
1. Read `data/leads/leads.json` — find leads with status=discovered (not yet drafted)
2. Sort by urgency score descending
3. For top 5 leads:
   a. Deep audit: `node forge.js audit --deep --url <url> --out data/sites/<date>-<slug>.json`
   b. Find 3 design references (structure/mood/motion): `node forge.js discover --site <url> --out data/references/<date>-<slug>.json`
   c. Generate blueprint: `node forge.js blueprint --audit <audit-path> --references <refs-path> --out data/blueprints/<date>-<slug>/`
   d. Get Design Judge approval: read blueprint, run rubric
   e. Write Gmail draft with personalized outreach
4. Update lead status to "drafted" in leads.json
5. Generate summary: 5 drafts created, key stats

## Rules
- NO_AUTOMATIC_SEND = true — Gmail drafts ONLY, never send
- Design Judge must approve each blueprint before drafting
- Personalization required — no template copy-paste

Your final response = the draft creation report.
