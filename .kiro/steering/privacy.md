---
inclusion: always
---

# Privacy rules (non-negotiable)

- **Images never leave the device.** Barcode decoding and OCR run in the browser.
- **Medication lists live in the browser by default.** API requests are stateless; the server does not persist a user's list unless the user explicitly donates it. The doctor note PDF is rendered in the browser.
- **No health data in logs.** Never log ingredients, ATC codes, product codes, events, dates, notes, or request bodies of medical endpoints. Log only request id, route, status, latency.
- **Donations require explicit, specific consent** and are anonymous: 5-year age band, optional sex, region (TR / EU / US only — no country, city or postcode), ingredients, event, direction (adverse/benefit), week of report. No names, emails, exact dates, locations or device identifiers. The user receives a deletion token; deletion must be complete.
- **Aggregates from user data:** never shown for groups smaller than **k = 20**; Laplace noise (differential privacy) is added to counts. FAERS counts are public data and need no noise.
- **QR tokens contain no personal data:** note id + HMAC signature + expiry only.

## Regional legal frame (design to all three)
- **EU — GDPR:** health data is a special category (Art. 9); donations rely on explicit consent; data minimisation, purpose limitation, right to erasure. Donated data is stored in an EU region.
- **Türkiye — KVKK:** health data is special-category personal data; explicit consent; same minimisation and erasure rules.
- **US:** Janus is not a HIPAA covered entity. Consumer health apps fall under FTC rules (the Health Breach Notification Rule's application to health apps changed in 2026 — re-check before launch) and state consumer-health-data laws. Follow the strictest rule set above everywhere.
- Say this plainly in the product's privacy page; never claim certification or compliance audits we have not done.
