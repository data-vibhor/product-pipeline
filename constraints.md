# Founder constraints

- Language: Python 3.12 with FastAPI. PostgreSQL for development and production.
- Data: hosted data must live in an external free database, not a local file on the web host.
- Hosting: free tiers only. Assume free servers sleep when idle. Do not name hosts that need a card or only offer trials.
- Scheduling: scheduled work runs from an external trigger and must tolerate delays of 30 minutes or more.
- No paid services in the MVP, including per-message fees.
- Never assume an external platform allows custom content or automation. Assume only documented options and list anything unverified as an open question.
- AI: use only free or open-weight models behind one provider interface so the model can be swapped. Every AI read of an invoice must be validated against a schema. A failed or low-confidence read goes to the owner for confirmation, never to a customer.
- AI never writes customer-facing text freely. Messages use fixed templates; the AI only fills in name, amount and dates.
- Payment status: only the owner confirms an invoice is paid.
- Input: invoices arrive as phone photos, scanned images, PDFs or CSV files, mostly from a phone. Support camera capture and file pick. Photos must be downscaled on the device before upload.
- Retention: original files are deleted after 30 days. Extracted fields are kept. The owner can download the original, or keep a copy on this device only, and the app must say that a device copy can be lost. The free file storage for originals is unverified and must be listed as an open question.
- Customer messaging, Phase 1: no automatic sending. Email, plus one-tap WhatsApp click-to-chat (wa.me) links with pre-filled text. Phone numbers in international format, digits only.
- Mobile first: design every screen for a phone first. Responsive web app, installable as a PWA, no native app. Do not assume the web share target works on iPhone; it is unverified.
- Indian law applies: DPDP Act 2023. Customers' personal data is processed for the owner only.
- Team: one solo founder, about 10 hours a day of build time.
