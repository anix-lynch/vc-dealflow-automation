# VC Deal Flow Automation — Apollo + Hunter + n8n + Claude

**Built by an ex-VC GP who managed 50+ portfolio companies across Southeast Asia.**

> This isn't a template. It's the actual system I wish existed when I was sourcing at Expara Venture Capital — rebuilt for the tools available today.

---

---

## Repository structure

```
vc-dealflow-automation/
├── airtable/
│   └── schema.json
├── n8n/
│   └── workflow.json
├── prompts/
│   └── outreach_personalization.md
├── scripts/
│   └── enrich_batch.py
└── README.md
```

## What This Does

End-to-end investor database enrichment, email verification, and personalized outreach automation for VC firms, family offices, and startup founders running investor relations at scale.

**The problem it solves:** Manually enriching 300 investor contacts, verifying emails, and writing personalized cold outreach takes a junior analyst 2–3 weeks. This system does it in under 2 hours.

### Core Pipeline

```
Apollo.io → [enrich contacts] → Hunter.io → [verify emails] → n8n → Claude API → [personalized outreach] → Airtable CRM
```

**Step by step:**

1. **Input** — CSV of raw contacts (name, firm, email or LinkedIn URL)
2. **Apollo.io enrichment** — pulls title, industry, company stage, AUM, portfolio focus
3. **Hunter.io verification** — confirms email deliverability before sending
4. **n8n orchestration** — routes valid contacts through the outreach pipeline
5. **Claude API personalization** — generates a bespoke first-line for each contact based on firm thesis and recent investments
6. **Airtable CRM** — logs every contact, enrichment status, and outreach in "Investor Pipeline" base
7. **Slack notification** — alerts #dealflow channel with a summary of new contacts processed

### Input → Output

| Input | Output |
|---|---|
| `contacts.csv` (name, firm, email) | `enriched_contacts.csv` with 15+ fields |
| Raw LinkedIn URL | Verified email + title + industry |
| Firm name | Personalized 3-sentence outreach message |
| Batch of 500 contacts | Airtable records + Slack digest in ~90 min |

---

## Stack

| Tool | Role |
|---|---|
| **Apollo.io** | Contact enrichment (title, firm data, social profiles) |
| **Hunter.io** | Email verification and deliverability scoring |
| **n8n** | Workflow orchestration (self-hosted or cloud) |
| **Claude API** | Personalized outreach generation (claude-3-5-sonnet) |
| **Airtable** | CRM — Investor Pipeline base |
| **Python 3.11** | Batch enrichment script for large datasets |
| **Slack** | Deal flow channel notifications |

---

## Repository Structure

```
vc-dealflow-automation/
├── README.md
├── n8n/
│   └── workflow.json          # Full n8n workflow — import directly
├── airtable/
│   └── schema.json            # Airtable base schema for Investor Pipeline
├── prompts/
│   └── outreach_personalization.md   # Claude prompt template with examples
└── scripts/
    └── enrich_batch.py        # Batch enrichment script (Apollo + Hunter)
```

---

## Setup Instructions

### Prerequisites
- Apollo.io account (Basic plan or higher for API access)
- Hunter.io account (Starter plan for email verification API)
- n8n instance (self-hosted via Docker or n8n.cloud)
- Anthropic API key (Claude API access)
- Airtable account with API key

### Step 1 — Clone and configure environment

```bash
git clone https://github.com/anix-lynch/vc-dealflow-automation
cd vc-dealflow-automation
```

Set environment variables (or add to `~/.config/secrets/global.env`):

```bash
export APOLLO_API_KEY=your_apollo_key
export HUNTER_API_KEY=your_hunter_key
export ANTHROPIC_API_KEY=your_claude_key
export AIRTABLE_API_KEY=your_airtable_key
export AIRTABLE_BASE_ID=your_base_id
export SLACK_WEBHOOK_URL=your_slack_webhook
```

### Step 2 — Install Python dependencies

```bash
pip install requests pandas python-dotenv tenacity
```

### Step 3 — Import n8n workflow

1. Open your n8n instance
2. Go to **Workflows → Import from File**
3. Upload `n8n/workflow.json`
4. Update credentials for: Apollo, Hunter, Claude (HTTP Header Auth), Airtable, Slack
5. Activate the workflow

### Step 4 — Set up Airtable base

1. Create a new Airtable base named **"Investor Pipeline"**
2. Reference `airtable/schema.json` to create all fields with correct types
3. Note your Base ID from the Airtable API docs URL
4. Set `AIRTABLE_BASE_ID` in your environment

### Step 5 — Run batch enrichment

```bash
# Prepare your input CSV: name,firm,email
# Example: contacts.csv

python scripts/enrich_batch.py --input contacts.csv --output enriched_contacts.csv
```

The script processes ~1 contact/second (rate-limited to respect API quotas). A 500-contact list takes ~8 minutes.

---

## Architecture Detail

### n8n Workflow Nodes

```
[Webhook Trigger]
    ↓
[Apollo.io — People Match API]     ← enriches: title, industry, seniority, company data
    ↓
[Hunter.io — Email Verifier API]   ← checks deliverability score
    ↓
[IF — email valid?]
    ↓ YES                              ↓ NO
[Set — compose contact object]     [Stop — log invalid]
    ↓
[Claude API — personalize message]
    ↓
[Airtable — create record]
    ↓
[Slack — notify #dealflow]
```

### Personalization Logic

Claude generates outreach using:
- Firm name and known portfolio companies (from Apollo enrichment)
- Contact's title and seniority level
- Industry vertical (FinTech / HealthTech / SaaS / DeepTech / Consumer)
- A system prompt trained on VC communication norms (see `prompts/outreach_personalization.md`)

The output is a 3-sentence first-line that references something specific about the firm — not a generic template.

---

## Live Demo

**[gozeroshot.dev](https://gozeroshot.dev)** — see the automation layer in production.

---

## Why This Exists

When I was a GP at Expara Venture Capital, our deal flow ops were a mess of spreadsheets, Gmail, and manual LinkedIn searches. We were tracking 200+ active portfolio touchpoints and sourcing from a network of 1,000+ founders and co-investors.

The enrichment and outreach problem is universal across VC: you have names, you need context, you need to move fast without sounding like a bot. This system solves that — at scale, with quality.

---

## Customization

This system is designed to be adapted:

- **Different CRM** — swap Airtable for HubSpot, Notion, or Salesforce by replacing the Airtable node
- **Different data source** — replace Apollo with LinkedIn Sales Navigator, Crunchbase, or PitchBook API
- **Email sending** — add a SendGrid or Instantly.ai node after the Claude step to send outreach directly
- **Scoring model** — add a Python function node to score contacts by ICP fit before routing to Claude

---

## License

MIT. Fork it, adapt it, ship it. If it closes a deal for you, I'd love to hear about it.

---

**Built by Anix Lynch | Ex-GP Expara Venture | MBA Chicago Booth | [gozeroshot.dev](https://gozeroshot.dev)**
