# Founder constraints

- Language: Python 3.12 with Flask or FastAPI. Use PostgreSQL for both development and production.
- Data: hosted data must live in an external free database, not a local file on the web host, because free hosts lose local files.
- Hosting: free tiers only. Assume free servers sleep when idle. Do not name hosts that need a card or only offer trials.
- Scheduling: scheduled work must run from an external trigger and must tolerate delays of 30 minutes or more. Never promise exact-minute timing.
- No paid services in the MVP. Platform fees such as per-message charges count as paid services.
- Never assume an external platform allows custom content or automation. Assume only documented options and list anything unverified as an open question.
- Customer messaging: no automatic sending in the MVP. The shopkeeper sends each reminder manually from their own WhatsApp using a click-to-chat link (wa.me) with pre-filled text. Phone numbers must be digits in international format.
- Indian law applies: DPDP Act 2023.
- Team: one solo founder, about 10 hours a day of build time.
