DesignForge lead discovery tick.

Workdir is the designforge repo root.

## Your Job
1. Use Exa/web search to find ugly/outdated websites in target industries
2. For each finding, audit using forge.js: `node forge.js audit --url <url> --out data/sites/<date>-<slug>.json`
3. Score: Commercial Fit (1-10), Visual Quality (1-10), Urgency (1-10)
4. Log top 50 leads to `data/leads/leads.json`
5. Generate summary: total found, top 3 by urgency, distribution by industry

## Rules
- Target industries: local business, SaaS, e-commerce, agency, professional services
- NO scraping of personal data
- NO auto-sending anything
- All leads logged to `data/leads/leads.json` with timestamp
- If < 10 leads found, expand search terms and try again

Your final response = the lead discovery report.
