DesignForge reply monitor tick.

Workdir is the designforge repo root.

## Your Job
1. Check Gmail inbox for replies to sent outreach drafts
2. Categorize each reply:
   - `interested` — wants to talk, ask about pricing, etc.
   - `not_interested` — no thanks
   - `maybe` — "not now but later" or asks for more info
   - `unsubscribe` — remove from list
3. For `interested` and `maybe` replies:
   - Send Discord notification via webhook
   - Update lead status in `data/leads/leads.json`
4. For `unsubscribe`: mark lead as `unsubscribed`, add to blocklist
5. Generate summary: replies today, interested count, unsubscribes

## Rules
- NEVER send auto-replies
- ALL unsubscribe requests honored immediately
- If no new replies, say so and stop

Your final response = the reply monitor report.
