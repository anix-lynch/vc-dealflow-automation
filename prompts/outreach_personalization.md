# Claude Prompt — Investor Outreach Personalization

Used in the n8n workflow at the **Claude — Generate Outreach Message** node.
Model: `claude-3-5-sonnet-20241022`
Max tokens: `400`
Temperature: default (1.0) — slight variation per message is intentional.

---

## System Prompt

```
You are a VC relationship manager with 10 years of experience at top-tier venture funds
in Southeast Asia and globally. You write warm, intelligent, non-spammy outreach messages
to investors, LPs, and founders.

Your messages are:
- Concise (2–3 sentences maximum)
- Specific to the firm and the person — never generic
- Peer-to-peer in tone — not vendor-to-buyer
- Free of hollow phrases like "I hope this finds you well", "I wanted to reach out",
  "synergies", or "pick your brain"
- Grounded in what the firm actually invests in or has recently done

You write from the perspective of Anix Lynch, ex-GP at Expara Venture Capital
(Southeast Asia, 50+ portfolio companies). She is reaching out to explore
co-investment opportunities, LP relationships, or deal flow sharing.

Respond with ONLY the body text — no subject line, no greeting, no sign-off.
Just the 2–3 sentence opening paragraph.
```

---

## User Prompt Template

```
Write a personalized cold outreach first paragraph for this investor contact:

Name: {{contact_name}}
Firm: {{firm_name}}
Title: {{title}}
Industry focus: {{industry}}
Location: {{city}}, {{country}}
Seniority: {{seniority}}

Context: I'm Anix Lynch, ex-GP at Expara Venture Capital (Southeast Asia, 50+ portfolio
companies). I'm reaching out to explore co-investment opportunities, LP relationships,
or deal flow sharing.

Keep it 2–3 sentences. Be specific to their firm and focus. No fluff.
```

---

## Variable Reference

| Variable | Source | Example |
|---|---|---|
| `{{contact_name}}` | Webhook input or Apollo enrichment | `Sarah Chen` |
| `{{firm_name}}` | Apollo enrichment → `organization.name` | `Sequoia Capital Southeast Asia` |
| `{{title}}` | Apollo enrichment → `person.title` | `Managing Partner` |
| `{{industry}}` | Apollo enrichment → `organization.industry` | `FinTech` |
| `{{city}}` | Apollo enrichment → `person.city` | `Singapore` |
| `{{country}}` | Apollo enrichment → `person.country` | `Singapore` |
| `{{seniority}}` | Apollo enrichment → `person.seniority` | `C-Suite / GP` |

---

## Example Input

```json
{
  "contact_name": "James Tan",
  "firm_name": "Golden Gate Ventures",
  "title": "Managing Partner",
  "industry": "SaaS",
  "city": "Singapore",
  "country": "Singapore",
  "seniority": "C-Suite / GP"
}
```

## Example Output

```
Golden Gate's focus on B2B SaaS infrastructure in Southeast Asia overlaps directly
with the operator-led deals we ran at Expara — particularly in the ERP and payments
layer. I'd love to compare notes on what you're seeing in the Series A pipeline and
explore whether there's any deal flow worth sharing bidirectionally.
```

---

## Tuning Notes

### When output is too generic
- Add more firm-specific context to the prompt: recent portfolio companies, known thesis statements, geography
- Enrich the Apollo payload further — pull `organization.short_description` or `organization.keywords` and include them in the prompt
- Lower temperature to 0.7 for more deterministic outputs

### When output is too long
- Add to the system prompt: `"Never exceed 60 words."`
- Hard-clip at the n8n Set node using: `{{ $json.body.content[0].text.split('.').slice(0, 3).join('.') + '.' }}`

### When output uses banned phrases
- Add an explicit prohibition list to the system prompt:
  ```
  Never use these phrases: "I hope this finds you well", "I wanted to reach out",
  "touch base", "pick your brain", "synergies", "circle back", "leverage",
  "at the end of the day", "game changer".
  ```

### Adjusting for different personas
- Replace the Expara context with the client's fund background
- Update the goal (co-investment / LP relationship / deal flow sharing) to match the actual ask
- For LP outreach (raising a fund), change the system prompt context from "co-investment" to "LP interest in Fund II"

### A/B testing
- Run two Claude calls with different system prompts and log both to Airtable (Claude Message A / Claude Message B)
- Track reply rates by Airtable Stage transitions to identify which prompt variant converts better

---

## Cost Reference (as of 2026-03)

| Model | Input tokens (est.) | Output tokens (est.) | Cost per message |
|---|---|---|---|
| claude-3-5-sonnet | ~300 | ~80 | ~$0.002 |
| claude-3-haiku | ~300 | ~80 | ~$0.0003 |

For batches of 500 contacts, total Claude cost is approximately **$1.00 on Sonnet**, **$0.15 on Haiku**.
Haiku is acceptable for high-volume batches; Sonnet recommended for senior GP / Partner contacts.
