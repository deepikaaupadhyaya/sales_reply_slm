# Quillmint sales-reply dataset (synthetic)

Fully synthetic data for a demo **sales-reply small language model (SLM)**. Every record is one moment where a reply was sent to a prospect. The task is to judge that reply and correct it if needed.

**No real data.** Quillmint, its founder "Mara", the product, prices, plans, policies and every conversation were written from scratch for this demo. IDs are random. People appear only as `[PERSON]`, and links as `[LINK]`.

## Contents

| File | What it is |
|---|---|
| `candidates.jsonl` | 81 records, one JSON object per line |
| `candidates-readable.json` | Same records, pretty-printed |
| `manifest.json` | Counts and SHA-256 checksum of `candidates.jsonl` |

## Scenario

Quillmint is an invented invoicing and expense app for freelancers and small studios. There are 4 campaigns:

| Campaign | Channel | What the bot does |
|---|---|---|
| `presales_chat` | web_chat | Answers pre-sales questions and hands off to a person when judgement is needed |
| `trial_onboarding_email` | email | Gets trial users to their first invoice |
| `demo_followup` | email | Closes open questions after a live demo |
| `partner_desk_email` | email | Invites accountants to a referral program |

The data has 28 threads and 26 prospects. Splits are made by thread, so no thread appears in two splits: train 64, validation 8, test 9.

## Record schema

```json
{
  "decision_id": "dec_…",
  "thread_id": "thr_…",
  "prospect_id": "pro_…",
  "campaign_id": "cmp_…",
  "campaign_name": "presales_chat",
  "channel": "web_chat | email",
  "trigger": "first_touch | scheduled_step | prospect_reply | human_outreach | human_takeover",
  "author": "ai | human | template",
  "history": [{"msg_id": "msg_…", "speaker": "prospect | ai | human | template", "sent_at": "ISO-8601", "text": "…"}],
  "response": {"msg_id": "msg_…", "sent_at": "ISO-8601", "text": "the reply being judged"},
  "campaign": {"objective": "…", "rules": ["…"], "facts": ["…"]},
  "split": "train | validation | test",
  "flags": ["synthetic", "empty_history", "history_truncated"],
  "review": {"status": "unreviewed", "label": null, "corrected_response": null}
}
```

- `history` holds up to the 10 messages before the response. The `history_truncated` flag marks records where older messages were dropped.
- `campaign.rules` is the bot's playbook. `campaign.facts` is the only source of truth the bot may answer from.

## Built-in labeling material

10 responses contain realistic mistakes for labelers to catch:

- a wrong price
- an invented feature
- an invented release date
- an invented discount
- a refund promised instead of handed off
- a pitch sent after an unsubscribe request
- a long reply that dodges the question
- a template sent twice
- an upgrade pushed when the problem was a bug

Most mistakes are followed by a human correction later in the thread. The mistakes are not labeled in the data on purpose.

## License

Synthetic, created for this project. Free to use under MIT.
