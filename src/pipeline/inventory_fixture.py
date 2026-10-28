"""Synthetic inventory-hallucination record used to test fact flags."""

INVENTORY_FIXTURE = {
    "decision_id": "dec_inventory_fixture",
    "thread_id": "thr_inventory_fixture",
    "prospect_id": "pro_inventory_fixture",
    "campaign_id": "cmp_d954e8192271",
    "campaign_name": "presales_chat",
    "channel": "web_chat",
    "trigger": "prospect_reply",
    "author": "ai",
    "history": [
        {
            "msg_id": "msg_inventory_q",
            "speaker": "prospect",
            "sent_at": "2026-03-01T10:00:00Z",
            "text": "Does Quillmint support inventory management? We need stock levels for the Studio plan.",
        }
    ],
    "response": {
        "msg_id": "msg_inventory_a",
        "sent_at": "2026-03-01T10:00:20Z",
        "text": "Yes — inventory management is included in the Studio plan. You can track stock levels alongside invoicing.\n\nQuill (Quillmint assistant)",
    },
    "campaign": {
        "objective": "Answer pre-sales questions from visitors on the pricing and features pages, qualify freelancers and small studios, and hand off to a person when the question needs judgement.",
        "rules": [
            "You are Quillmint's website assistant. Answer only from the Product Facts. If the facts don't cover it, say you'll check with the team and set handoff.",
            "Keep replies under 60 words. Ask at most one question back.",
            "Never invent discounts, features or release dates. Quote prices exactly as listed.",
            "Set handoff for: refunds, billing disputes, tax or legal advice, account or data deletion, security and compliance paperwork, anything about a specific invoice.",
            "If the visitor mentions 5 or more people on their team, offer a 15-minute fit call: [LINK]",
            "Reply in Spanish or Portuguese if the visitor writes in it; otherwise reply in English.",
            "Sign off as 'Quill (Quillmint assistant)'. No emojis.",
        ],
        "facts": [
            "Plans: Free = 3 invoices per month, 1 currency. Solo = $11/month: unlimited invoices, receipt scanning, up to 5 currencies. Studio = $27/month: up to 4 seats, client portal, automatic payment reminders, all currencies. Agency = $64/month: up to 15 seats, assisted migration, API access.",
            "Annual billing gives 2 months free (Solo $110/yr, Studio $270/yr, Agency $640/yr).",
            "Trial: 21 days of Studio, no card required. When it ends the workspace drops to Free unless the user picks a plan; nothing is deleted.",
            "Receipt scanning: snap a photo in the mobile app or forward the email to your personal receipts@ address. Extracts vendor, date, total and tax amount.",
            "Payment reminders (Studio and above): up to 3 scheduled reminders per invoice, wording editable.",
            "Exports: CSV and PDF on every plan. Accountant access: read-only seat, free, on Solo and above (also during the trial).",
            "Import: CSV import for clients and past invoices on all paid plans; Agency includes assisted migration by the team.",
            "Tax: Quillmint supports reverse-charge and tax-exempt line items but does not give tax advice.",
            "Not available: payroll, inventory, time tracking. Time tracking is on the roadmap with no date.",
            "Data is hosted in the EU (Frankfurt). A DPA is available on request from the team.",
            "Refunds: within 14 days of the first charge. Handled by a human only.",
            "No standard discounts beyond annual billing. Any other discount needs a human.",
            "Mobile apps on iOS and Android.",
        ],
    },
    "split": "test",
    "flags": ["synthetic", "pipeline_fixture"],
    "review": {"status": "unreviewed", "label": None, "corrected_response": None},
}

INVENTORY_CORRECTION = "Inventory management is not currently available in Quillmint."
